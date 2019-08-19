from datetime import timedelta
import json
import re
import pandas as pd
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
    Http404,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import status
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from cjworkbench.types import ProcessResult
from server.models import WfModule
from server import rabbitmq
import server.utils
from server.models.loaded_module import module_get_html_bytes


_MaxNRowsPerRequest = 300


def _lookup_wf_module(pk: int) -> WfModule:
    """Find a Workflow and WfModule based on pk (no access control).

    Raises Http404 if pk is not found in the database.
    """
    wf_module = get_object_or_404(WfModule, pk=pk, is_deleted=False)

    # Look up workflow now, so we don't look it up later
    if not wf_module.workflow:
        # We can't read the data in here, because we don't know the workflow so
        # we can't lock it.
        raise Http404()

    return wf_module


def _lookup_wf_module_for_read(pk: int, request: HttpRequest) -> WfModule:
    """Find a WfModule based on pk.

    Raises Http404 if pk is not found in the database, or PermissionDenied if
    the person requesting does not have read access.
    """
    wf_module = _lookup_wf_module(pk)  # or raise Http404

    if not wf_module.workflow.request_authorized_read(request):
        raise PermissionDenied()

    return wf_module


def _lookup_wf_module_for_write(pk: int, request: HttpRequest) -> WfModule:
    """Find a WfModule based on pk.

    Raises Http404 if pk is not found in the database, or PermissionDenied if
    the person requesting does not have write access.
    """
    wf_module = _lookup_wf_module(pk)  # or raise Http404

    if not wf_module.workflow.request_authorized_write(request):
        raise PermissionDenied()

    return wf_module


# ---- render / input / livedata ----
# These endpoints return actual table data

# Helper method that produces json output for a table + start/end row
# Also silently clips row indices
# Now reading a maximum of 101 columns directly from cache parquet
def _make_render_tuple(cached_result, startrow=None, endrow=None):
    """Build (startrow, endrow, json_rows) data."""
    if not cached_result:
        dataframe = pd.DataFrame()
    else:
        columns = cached_result.columns[
            # Return one row more than configured, so the client knows there
            # are "too many rows".
            : (settings.MAX_COLUMNS_PER_CLIENT_REQUEST + 1)
        ]
        column_names = [c.name for c in columns]
        dataframe = cached_result.read_dataframe(column_names)

    nrows = len(dataframe)
    if startrow is None:
        startrow = 0
    if endrow is None:
        endrow = startrow + _MaxNRowsPerRequest

    startrow = max(0, startrow)
    endrow = min(nrows, endrow, startrow + _MaxNRowsPerRequest)

    table = dataframe[startrow:endrow]

    # table.to_json() renders a JSON string. It can't render a dict that we
    # encode later, so let's not even try. Just return the string.
    rows = table.to_json(orient="records", date_format="iso")
    return (startrow, endrow, rows)


def int_or_none(x):
    return int(x) if x is not None else None


# /render: return output table of this module
@api_view(["GET"])
@renderer_classes((JSONRenderer,))
def wfmodule_render(request, pk, format=None):
    wf_module = _lookup_wf_module_for_read(pk, request)

    # Get first and last row from query parameters, or default to all if not
    # specified
    try:
        startrow = int_or_none(request.GET.get("startrow"))
        endrow = int_or_none(request.GET.get("endrow"))
    except ValueError:
        return Response(
            {"message": "bad row number", "status_code": 400},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with wf_module.workflow.cooperative_lock():
        wf_module.refresh_from_db()
        cached_result = wf_module.cached_render_result
        if cached_result is None:
            # assume we'll get another request after execute finishes
            return JsonResponse({"start_row": 0, "end_row": 0, "rows": []})

        startrow, endrow, rows_string = _make_render_tuple(
            cached_result, startrow, endrow
        )
        return HttpResponse(
            "".join(
                [
                    '{"start_row":',
                    str(startrow),
                    ',"end_row":',
                    str(endrow),
                    ',"rows":',
                    rows_string,
                    "}",
                ]
            ),
            content_type="application/json",
        )


_html_head_start_re = re.compile(rb"<\s*head[^>]*>", re.IGNORECASE)


@api_view(["GET"])
@xframe_options_exempt
def wfmodule_output(request, pk, format=None):
    wf_module = _lookup_wf_module_for_read(pk, request)

    html = module_get_html_bytes(wf_module.module_version)

    return HttpResponse(content=html)


@api_view(["GET"])
@renderer_classes((JSONRenderer,))
def wfmodule_embeddata(request, pk):
    wf_module = _lookup_wf_module_for_read(pk, request)

    # Speedy bypassing of locks: we don't care if we get out-of-date data
    # because we assume the client will re-request when it gets a new
    # cached_render_result_delta_id.
    try:
        result_json = json.loads(
            bytes(wf_module.cached_render_result_json), encoding="utf-8"
        )
    except ValueError:
        result_json = None

    return JsonResponse(result_json, safe=False)


@api_view(["GET"])
@renderer_classes((JSONRenderer,))
def wfmodule_value_counts(request, pk):
    wf_module = _lookup_wf_module_for_read(pk, request)

    try:
        colname = request.GET["column"]
    except KeyError:
        return JsonResponse({"error": 'Missing a "column" parameter'}, status=400)

    if not colname:
        # User has not yet chosen a column. Empty response.
        return JsonResponse({"values": {}})

    with wf_module.workflow.cooperative_lock():
        wf_module.refresh_from_db()
        cached_result = wf_module.cached_render_result
        if cached_result is None:
            # assume we'll get another request after execute finishes
            return JsonResponse({"values": {}})

        try:
            column = next(c for c in cached_result.columns if c.name == colname)
        except StopIteration:
            return JsonResponse({"error": f'column "{colname}" not found'}, status=404)

        # Only load the one column
        dataframe = cached_result.read_dataframe([colname])
        try:
            series = dataframe[colname]
        except KeyError:
            # Cache has disappeared. (read_dataframe() returns empty DataFrame
            # instead of throwing, as it maybe ought to.) We're probably going
            # to make another request soon.
            return JsonResponse({"error": f'column "{colname}" not found'}, status=404)

    # We only handle string. If it's not string, convert to string. (Rationale:
    # this is used in Refine and Filter by Value, which are both solely
    # String-based for now. Excel and Google Sheets only filter by String
    # values, so we're in good company.) Remember: in JavaScript, Object keys
    # must be String.
    series = column.type.format_series(series)
    value_counts = series.value_counts().to_dict()

    return JsonResponse({"values": value_counts})


N_ROWS_PER_TILE = 200
N_COLUMNS_PER_TILE = 50


@api_view(["GET"])
def wfmodule_tile(request, pk, delta_id, tile_row, tile_column):
    wf_module = _lookup_wf_module_for_read(pk, request)

    if str(wf_module.last_relevant_delta_id) != delta_id:
        return HttpResponseNotFound(
            f"Requested delta {delta_id} but wf_module is "
            f"at delta {wf_module.last_relevant_delta_id}"
        )

    if wf_module.status != "ok":
        return HttpResponseNotFound(
            f'Requested wf_module has status "{wf_module.status}" but '
            'we only render "ok" modules'
        )

    # Don't bother with workflow lock. Instead, handle FileNotFoundError if it
    # comes up.
    cached_result = wf_module.cached_render_result

    if cached_result is None:
        return HttpResponseNotFound(f"This module has no cached result")

    if str(cached_result.delta_id) != delta_id:
        return HttpResponseNotFound(
            f"Requested delta {delta_id} but cached render result is "
            f"at delta {cached_result.delta_id}"
        )

    # cbegin/cend: column indexes
    cbegin = N_COLUMNS_PER_TILE * int(tile_column)
    cend = N_COLUMNS_PER_TILE * (int(tile_column) + 1)

    # TODO handle races in the following file reads....
    df = cached_result.read_dataframe(columns=cached_result.column_names[cbegin:cend])

    rbegin = N_ROWS_PER_TILE * int(tile_row)
    rend = N_ROWS_PER_TILE * (int(tile_row) + 1)

    df = df.iloc[rbegin:rend]

    json_string = df.to_json(orient="values", date_format="iso")

    return HttpResponse(json_string, content_type="application/json")


# Public access to wfmodule output. Basically just /render with different auth
# and output format
# NOTE: does not support startrow/endrow at the moment
@api_view(["GET"])
@renderer_classes((JSONRenderer,))
def wfmodule_public_output(request, pk, type, format=None):
    wf_module = _lookup_wf_module_for_read(pk, request)
    workflow = wf_module.workflow

    with workflow.cooperative_lock():
        wf_module.refresh_from_db()
        cached_result = wf_module.cached_render_result
        if cached_result:
            result = cached_result.result  # slow! Reads from S3
        else:
            # We don't have a cached result, and we don't know how long it'll
            # take to get one.
            async_to_sync(rabbitmq.queue_render)(workflow.id, workflow.last_delta_id)
            # The user will simply need to try again....
            result = ProcessResult()

    if type == "json":
        d = result.dataframe.to_json(orient="records")
        return HttpResponse(d, content_type="application/json")
    elif type == "csv":
        d = result.dataframe.to_csv(index=False)
        return HttpResponse(d, content_type="text/csv")
    else:
        raise Http404()
