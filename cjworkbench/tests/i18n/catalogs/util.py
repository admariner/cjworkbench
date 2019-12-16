import unittest
from babel.messages.catalog import Catalog, Message
from cjworkbench.i18n.catalogs.util import (
    message_unique_identifier,
    find_corresponding_message,
    find_corresponding_string,
    find_fuzzy_messages,
    copy_message,
    add_or_update_message,
    fill_catalog,
    mark_fuzzy,
    remove_strings,
)
from cjworkbench.i18n.catalogs.merge import _merge_source_catalog, _merge_catalog


def assert_catalogs_deeply_equal(
    catalog: Catalog, other_catalog: Catalog, msg: str = ""
):
    """ Assert that the two catalogs contain the same messages, where message equality is deep.
    
    Ignores header message.
    """
    msg = f"{msg}: " if msg else ""
    assert_catalog_deeply_contains_catalog(
        catalog,
        other_catalog,
        msg=f"{msg}The first catalog is not included in the second",
    )
    assert_catalog_deeply_contains_catalog(
        other_catalog,
        catalog,
        msg=f"{msg}The second catalog is not included in the first",
    )


def assert_catalog_deeply_contains_catalog(
    catalog: Catalog, other_catalog: Catalog, msg: str = ""
):
    """ Assert that `other_catalog` contains all the messages of `catalog`, where message equality is deep.
    
    Ignores header message.
    """
    tc = unittest.TestCase()
    msg = f"{msg}: " if msg else ""
    tc.assertEqual(
        catalog.locale,
        other_catalog.locale,
        msg=f"{msg}The two catalogs have different locales",
    )
    for message in catalog:
        if message.id:  # ignore header
            other_message = find_corresponding_message(other_catalog, message)
            tc.assertTrue(
                other_message, msg=f"{msg}Message {message} not found in catalog"
            )
            assert_messages_deeply_equal(
                message,
                other_message,
                msg=f"{msg}The two catalogs have different properties in a message",
            )


def assert_messages_deeply_equal(
    message: Message, other_message: Message, msg: str = ""
):
    tc = unittest.TestCase()
    msg = f"{msg}: " if msg else ""
    tc.assertEqual(
        message,
        other_message,
        msg=f"{msg}The two messages have different ID and/or context: {message} (with context {message.context}), {other_message} (with context {other_message.context})",
    )  # this compares id and context
    tc.assertEqual(
        message.string,
        other_message.string,
        msg=f"{msg}The two messages have different string: {message} has {message.string}, {other_message} has {other_message.string}",
    )
    tc.assertEqual(
        message.flags,
        other_message.flags,
        msg=f"{msg}The two messages have different flags: {message} has {message.flags}, {other_message} has {other_message.flags}",
    )
    tc.assertEqual(
        message.auto_comments,
        other_message.auto_comments,
        msg=f"{msg}The two messages have different auto_comments: {message} has {message.auto_comments}, {other_message} has {other_message.auto_comments}",
    )
    tc.assertEqual(
        message.user_comments,
        other_message.user_comments,
        msg=f"{msg}The two messages have different user_comments: {message} has user_comments {message.user_comments}, {other_message} has {other_message.user_comments}",
    )
    tc.assertEqual(
        message.locations,
        other_message.locations,
        msg=f"{msg}The two messages have different locations: {message} has {message.locations}, {other_message} has {other_message.locations}",
    )


class UtilTest(unittest.TestCase):
    def test_message_unique_identifier_no_context(self):
        self.assertEqual(message_unique_identifier(Message("id", string="Text")), "id")

    def test_message_unique_identifier_with_context(self):
        self.assertEqual(
            message_unique_identifier(Message("id", string="Text", context="ctxt")),
            ("id", "ctxt"),
        )

    def test_find_corresponding_message_exists(self):
        catalog = Catalog()
        catalog.add("id", string="Text")
        corresponding = find_corresponding_message(catalog, Message("id"))
        self.assertTrue(corresponding)
        assert_messages_deeply_equal(corresponding, catalog.get("id"))
        self.assertEqual(find_corresponding_string(catalog, Message("id")), "Text")

    def test_find_corresponding_message_with_context_exists(self):
        catalog = Catalog()
        catalog.add("id", string="Text", context="ctxt")
        corresponding = find_corresponding_message(
            catalog, Message("id", context="ctxt")
        )
        self.assertTrue(corresponding)
        assert_messages_deeply_equal(corresponding, catalog.get("id", context="ctxt"))
        self.assertEqual(
            find_corresponding_string(catalog, Message("id", context="ctxt")), "Text"
        )

    def test_find_corresponding_message_not_exists(self):
        catalog = Catalog()
        catalog.add("id", string="Text")
        corresponding = find_corresponding_message(catalog, Message("other id"))
        self.assertIsNone(corresponding)
        self.assertIsNone(find_corresponding_string(catalog, Message("other id")))

    def test_find_corresponding_message_with_context_not_exists(self):
        catalog = Catalog()
        catalog.add("id", string="Text")
        corresponding = find_corresponding_message(
            catalog, Message("id", context="ctxt")
        )
        self.assertIsNone(corresponding)
        self.assertIsNone(
            find_corresponding_string(catalog, Message("other id", context="ctxt"))
        )

    def test_remove_strings(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        old_catalog.add("id2", string="Text1", context="ctxt")
        remove_strings(old_catalog)
        expected_catalog = Catalog()
        expected_catalog.add("id1", string="")
        expected_catalog.add("id2", string="", context="ctxt")
        assert_catalogs_deeply_equal(old_catalog, expected_catalog)

    def test_find_fuzzy_messages_fuzzy(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        new_catalog = Catalog()
        new_catalog.add("id1", string="Text1new")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(["id1"]),
        )

    def test_find_fuzzy_messages_fuzzy_with_context(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1", context="ctxt")
        new_catalog = Catalog()
        new_catalog.add("id1", string="Text1new", context="ctxt")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset([("id1", "ctxt")]),
        )

    def test_find_fuzzy_messages_fuzzy_multiple(self):
        old_catalog = Catalog()
        old_catalog.add("id0", string="Text1")
        old_catalog.add("id1", string="Text1")
        old_catalog.add("id2", string="Text1", context="ctxt1")
        old_catalog.add("id2", string="Text1", context="ctxt2")
        new_catalog = Catalog()
        new_catalog.add("id0", string="Text1")
        new_catalog.add("id1", string="Text1new")
        new_catalog.add("id2", string="Text1new", context="ctxt1")
        new_catalog.add("id2", string="Text1new", context="ctxt2")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(["id1", ("id2", "ctxt1"), ("id2", "ctxt2")]),
        )

    def test_find_fuzzy_messages_ignore_same(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        new_catalog = Catalog()
        new_catalog.add("id1", string="Text1")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(),
        )

    def test_find_fuzzy_messages_ignore_already_fuzzy(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1", flags=["fuzzy"])
        new_catalog = Catalog()
        new_catalog.add("id1", string="Text1", flags=["fuzzy"])
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(),
        )

    def test_find_fuzzy_messages_ignore_new(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        new_catalog = Catalog()
        new_catalog.add("id2", string="Text1")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(),
        )

    def test_find_fuzzy_messages_ignore_context_add(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        new_catalog = Catalog()
        new_catalog.add("id1", string="Text1", context="ctxt")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(),
        )

    def test_find_fuzzy_messages_ignore_empty_old(self):
        old_catalog = Catalog()
        old_catalog.add("id1", string="")
        new_catalog = Catalog()
        old_catalog.add("id1", string="Text1")
        self.assertEqual(
            find_fuzzy_messages(old_catalog=old_catalog, new_catalog=new_catalog),
            frozenset(),
        )

    def test_copy_message_copies(self):
        old_message = Message("id", string="a", locations=[("file1", "2")])
        new_message = copy_message(old_message)
        expected_message = Message("id", string="a", locations=[("file1", "2")])
        assert_messages_deeply_equal(new_message, expected_message)

    def test_copy_message_replaces_string(self):
        old_message = Message("id", string="a", locations=[("file1", "2")])
        new_message = copy_message(old_message, string="b")
        expected_message = Message("id", string="b", locations=[("file1", "2")])
        assert_messages_deeply_equal(new_message, expected_message)

    def test_add_or_update_message_add(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        add_or_update_message(target_catalog, Message("id2", string="Text2"))

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1")
        expected_catalog.add("id2", string="Text2")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_add_or_update_message_add_with_context(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        add_or_update_message(
            target_catalog, Message("id2", string="Text2", context="ctxt2")
        )

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1")
        expected_catalog.add("id2", string="Text2", context="ctxt2")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_add_or_update_message_update(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        add_or_update_message(target_catalog, Message("id1", string="Text2"))

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text2")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_add_or_update_message_add_with_context(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1", context="ctxt")

        add_or_update_message(
            target_catalog, Message("id1", string="Text2", context="ctxt")
        )

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text2", context="ctxt")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_preserve_old(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()

        string_source_catalog = Catalog()

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_update_message(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()
        source_catalog.add("id1", string="Text1")

        string_source_catalog = Catalog()
        string_source_catalog.add("id1", string="Text2")

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text2")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_add_new(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()
        source_catalog.add("id2", string="Text2ignore")

        string_source_catalog = Catalog()
        string_source_catalog.add("id2", string="Text2")

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1")
        expected_catalog.add("id2", string="Text2")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_add_new_no_new_string(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()
        source_catalog.add("id1", string="Text1ignore")
        source_catalog.add("id2", string="Text2ignore")

        string_source_catalog = Catalog()
        string_source_catalog.add("id3", string="Text3")

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1")
        expected_catalog.add("id2", string="")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_get_properties(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()
        source_catalog.add("id1", string="Text1ignore", auto_comments=["comment"])
        source_catalog.add("id2", string="Text2ignore", locations=[("file1", "1")])

        string_source_catalog = Catalog()
        string_source_catalog.add(
            "id1",
            string="Text1new",
            auto_comments=["comment2"],
            locations=[("file2", "1")],
        )

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1new", auto_comments=["comment"])
        expected_catalog.add("id2", string="", locations=[("file1", "1")])

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_update_properties(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1", auto_comments=["comment"])

        source_catalog = Catalog()
        source_catalog.add("id1", string="Text1ignore", auto_comments=["new comment"])

        string_source_catalog = Catalog()

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1", auto_comments=["new comment"])

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_fill_catalog_protects_sources(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        source_catalog = Catalog()
        source_catalog.add("id1", string="Text1ignore", auto_comments=["comment"])
        source_catalog.add("id2", string="Text2ignore", locations=[("file1", "1")])

        string_source_catalog = Catalog()
        string_source_catalog.add(
            "id1",
            string="Text1new",
            auto_comments=["comment2"],
            locations=[("file2", "1")],
        )

        fill_catalog(target_catalog, source_catalog, string_source_catalog)

        expected_source_catalog = Catalog()
        expected_source_catalog.add(
            "id1", string="Text1ignore", auto_comments=["comment"]
        )
        expected_source_catalog.add(
            "id2", string="Text2ignore", locations=[("file1", "1")]
        )
        assert_catalogs_deeply_equal(source_catalog, expected_source_catalog)

        expected_string_source_catalog = Catalog()
        expected_string_source_catalog.add(
            "id1",
            string="Text1new",
            auto_comments=["comment2"],
            locations=[("file2", "1")],
        )
        assert_catalogs_deeply_equal(
            string_source_catalog, expected_string_source_catalog
        )

    def test_mark_fuzzy_mark_new(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1")

        old_catalog = Catalog()

        fuzzy = frozenset(["id1"])

        mark_fuzzy(target_catalog, fuzzy, old_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1", flags=["fuzzy"])

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_mark_fuzzy_mark_old(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="Text1", flags=["fuzzy"])

        old_catalog = Catalog()

        fuzzy = frozenset()

        mark_fuzzy(target_catalog, fuzzy, old_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="Text1", flags=["fuzzy"])

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)

    def test_mark_fuzzy_no_mark_empty(self):
        target_catalog = Catalog()
        target_catalog.add("id1", string="")

        old_catalog = Catalog()

        fuzzy = frozenset(["id1"])

        mark_fuzzy(target_catalog, fuzzy, old_catalog)

        expected_catalog = Catalog()
        expected_catalog.add("id1", string="")

        assert_catalogs_deeply_equal(target_catalog, expected_catalog)


class MergeTest(unittest.TestCase):
    def test_merge_source_catalog_parse_python_special_comments(self):
        js_catalog = Catalog("en")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            locations=[("file1", "1")],
            auto_comments=["default-message: Text1", "some comment"],
        )
        old_source_catalog = Catalog("en")

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset())

    def test_merge_source_catalog_add_js_and_python(self):
        js_catalog = Catalog("en")
        js_catalog.add(
            "id0",
            string="Text0",
            locations=[("file0", "2")],
            auto_comments=["some js comment"],
        )
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            locations=[("file1", "1")],
            auto_comments=["default-message: Text1", "some comment"],
        )
        old_source_catalog = Catalog("en")

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id0",
            string="Text0",
            locations=[("file0", "2")],
            auto_comments=["some js comment"],
        )
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset())

    def test_merge_source_catalog_update_existing_old(self):
        js_catalog = Catalog("en")
        js_catalog.add(
            "id0",
            string="Text0",
            locations=[("file0", "2")],
            auto_comments=["some js comment"],
        )
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            locations=[("file1", "1")],
            auto_comments=["default-message: Text1", "some comment"],
        )
        old_source_catalog = Catalog("en")
        old_source_catalog.add(
            "id0",
            string="Text0",
            locations=[("file0", "3")],
            auto_comments=["some js comment"],
        )
        old_source_catalog.add(
            "id1",
            string="Text1",
            locations=[("file0", "2")],
            auto_comments=["some old comment"],
        )

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id0",
            string="Text0",
            locations=[("file0", "2")],
            auto_comments=["some js comment"],
        )
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset())

    def test_merge_source_catalog_remove_deprecated_old(self):
        js_catalog = Catalog("en")
        js_catalog.add(
            "id0", locations=[("file0", "2")], auto_comments=["some js comment"]
        )
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            locations=[("file1", "1")],
            auto_comments=["default-message: Text1", "some comment"],
        )
        old_source_catalog = Catalog("en")
        old_source_catalog.add(
            "id2", locations=[("file1", "1")], auto_comments=["some comment"]
        )

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id0", locations=[("file0", "2")], auto_comments=["some js comment"]
        )
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset())

    def test_merge_source_catalog_fuzzy_in_python(self):
        js_catalog = Catalog("en")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            locations=[("file1", "1")],
            auto_comments=["default-message: Text1", "some comment"],
        )
        old_source_catalog = Catalog("en")
        old_source_catalog.add(
            "id1",
            string="Text0",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset(["id1"]))

    def test_merge_source_catalog_fuzzy_in_js(self):
        js_catalog = Catalog("en")
        js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        python_catalog = Catalog("en")
        old_source_catalog = Catalog("en")
        old_source_catalog.add(
            "id1",
            string="Text0",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )

        new_js_catalog, new_python_catalog, fuzzy = _merge_source_catalog(
            js_catalog, python_catalog, old_source_catalog
        )

        expected_python_catalog = Catalog("en")
        expected_js_catalog = Catalog("en")
        expected_js_catalog.add(
            "id1",
            string="Text1",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        assert_catalogs_deeply_equal(new_js_catalog, expected_js_catalog)
        assert_catalogs_deeply_equal(new_python_catalog, expected_python_catalog)
        self.assertEqual(fuzzy, frozenset(["id1"]))

    def test_merge_catalog_add_from_python(self):
        js_catalog = Catalog("el")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            string="Text0",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        old_catalog = Catalog("el")
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_python(self):
        js_catalog = Catalog("el")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            string="Text1",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text0",
            locations=[("file3", "2")],
            auto_comments=["some old comment"],
        )
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text0",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_add_from_js(self):
        js_catalog = Catalog("el")
        js_catalog.add(
            "id1", string="", locations=[("file1", "1")], auto_comments=["some comment"]
        )
        python_catalog = Catalog("en")
        old_catalog = Catalog("el")
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1", string="", locations=[("file1", "1")], auto_comments=["some comment"]
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_js(self):
        js_catalog = Catalog("el")
        js_catalog.add(
            "id1",
            string="",
            locations=[("file2", "2")],
            auto_comments=["some new comment"],
        )
        python_catalog = Catalog("en")
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text2",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text2",
            locations=[("file2", "2")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_python_fuzzy_old(self):
        js_catalog = Catalog("el")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            string="Text2",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text0",
            flags=["fuzzy"],
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text0",
            flags=["fuzzy"],
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_python_fuzzy_new(self):
        js_catalog = Catalog("el")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            string="Text0",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text2",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        fuzzy = frozenset(["id1"])

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text2",
            flags=["fuzzy"],
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_python_fuzzy_empty(self):
        js_catalog = Catalog("el")
        python_catalog = Catalog("en")
        python_catalog.add(
            "id1",
            string="Text0",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1", string="", locations=[("file1", "1")], auto_comments=["some comment"]
        )
        fuzzy = frozenset(["id1"])

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_js_fuzzy_old(self):
        js_catalog = Catalog("el")
        js_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        python_catalog = Catalog("en")
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text0",
            flags=["fuzzy"],
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        fuzzy = frozenset()

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text0",
            flags=["fuzzy"],
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_js_fuzzy_new(self):
        js_catalog = Catalog("el")
        js_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        python_catalog = Catalog("en")
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1",
            string="Text2",
            locations=[("file1", "1")],
            auto_comments=["some comment"],
        )
        fuzzy = frozenset(["id1"])

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="Text2",
            flags=["fuzzy"],
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)

    def test_merge_catalog_update_from_js_fuzzy_empty(self):
        js_catalog = Catalog("el")
        js_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        python_catalog = Catalog("en")
        old_catalog = Catalog("el")
        old_catalog.add(
            "id1", string="", locations=[("file1", "1")], auto_comments=["some comment"]
        )
        fuzzy = frozenset(["id1"])

        new_catalog = _merge_catalog(js_catalog, python_catalog, old_catalog, fuzzy)

        expected_catalog = Catalog("el")
        expected_catalog.add(
            "id1",
            string="",
            locations=[("file2", "1")],
            auto_comments=["some new comment"],
        )
        assert_catalogs_deeply_equal(new_catalog, expected_catalog)