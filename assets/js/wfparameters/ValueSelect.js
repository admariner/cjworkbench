import React from 'react'
import PropTypes from 'prop-types'
import { withFetchedData } from './FetchedData'
import { List } from 'react-virtualized'
import memoize from 'memoize-one'

const NumberFormatter = new Intl.NumberFormat()

// TODO: Change class names to move away from Refine and update CSS

/**
 * Displays a list item of check box, name (of value), and count
 */
class ValueItem extends React.PureComponent {
  static propTypes = {
    name: PropTypes.string, // new value -- may be empty string
    count: PropTypes.number.isRequired, // number, strictly greater than 0
    isSelected: PropTypes.bool.isRequired,
    onChangeIsSelected: PropTypes.func.isRequired // func(name, isSelected) => undefined
  }

  onChangeIsSelected = (ev) => {
    this.props.onChangeIsSelected(this.props.name, ev.target.checked)
  }

  render () {
    const { count, name } = this.props
    const className = 'visible original'

    return (
      <li className={className}>
        <div className='summary'>
          <input
            name={`include[${name}]`}
            type='checkbox'
            title='Include these rows'
            checked={this.props.isSelected}
            onChange={this.onChangeIsSelected}
          />
          <div className="container">
            <span className='value'>{name}</span>
            <span className='count'>{NumberFormatter.format(count)}</span>
          </div>
        </div>
      </li>
    )
  }
}

export class AllNoneButtons extends React.PureComponent {
  static propTypes = {
    isReadOnly: PropTypes.bool.isRequired,
    clearSelectedValues: PropTypes.func.isRequired, // func() => undefined
    fillSelectedValues: PropTypes.func.isRequired // func() => undefined
  }

  render() {
    const { isReadOnly, clearSelectedValues, fillSelectedValues } = this.props

    return (
      <div className="all-none-buttons">
        <button
          disabled={isReadOnly}
          name='refine-select-all'
          title='Select All'
          onClick={fillSelectedValues}
          className='mc-select-all'
        >
          All
        </button>
        <button
          disabled={isReadOnly}
          name='refine-select-none'
          title='Select None'
          onClick={clearSelectedValues}
          className='mc-select-none'
        >
          None
        </button>
      </div>
    )
  }
}

/**
 * The "value" here is a JSON-encoded String: `["value1", "value2"]`
 *
 * `valueCounts` describes the input: `{ "foo": 1, "bar": 3, ... }`
 *
 * A JSON encoded string of _checked_ items is returned through onChange(): `["value1", "value2", value5"]`
 */
export class ValueSelect extends React.PureComponent {
  static propTypes = {
    valueCounts: PropTypes.object, // null or { value1: n, value2: n, ... }
    loading: PropTypes.bool.isRequired, // true iff loading from server
    value: PropTypes.string.isRequired, // JSON-encoded `["value1", "value2"]}`
    onChange: PropTypes.func.isRequired // fn(JSON.stringify(['value1', 'value2', 'value5']))
  }
  /** searchInput is the textbox string input from the user **/
  state = {
    searchInput: ''
  }
  /** references valueComponents, list of ValueItem to be consumed by 'renderRow()' **/
  valueComponentsRef = React.createRef()
  /** references virtualized valueList to force re-render in 'onChange()' when an item is checked/unchecked **/
  valueListRef = React.createRef()

  /**
   * Return "selectedValues" in object form for fast lookup:
   *
   * {value1: null, value2: null, value5: null}
   */
  get selectedValues () {
    if (this.props.value) return this.selectedValuesObject(this.props.value)
    return {}
  }

  /** takes JSON encoded `[value1, value2]` and maps to {value1: null, value2: null} **/
  selectedValuesObject = memoize(values => {
    const selectedList = JSON.parse(values)
    let selectedValues = {}
    for (const index in selectedList) {
      selectedValues[selectedList[index]] = null
    }
    return selectedValues
  })

  onReset = () => {
    this.setState({ searchInput: '' })
  }

  onKeyDown = (ev) => {
    if (ev.keyCode === 27) this.onReset() // Esc => reset
  }

  onInputChange = (ev) => {
    const searchInput = ev.target.value
    this.setState({ searchInput })
  }

  /** convert {value1: null, value2: null} to JSON encoded ['value1', 'value2'] to return **/
  onChange = (selectedValues) => {
    const json = this.toJsonString(selectedValues)
    this.props.onChange(json)
    this.valueListRef.forceUpdateGrid()
  }

  toJsonString = (selectedValues) => {
    const json = JSON.stringify(Object.keys(selectedValues))
    return json
  }

  /** Reduce list from valueCounts to only match search input for faster rendering of ValueItem list**/
  valueMatching = (searchInput) => {
    let valueCounts = Object.assign({}, this.props.valueCounts)
    const searchKey = searchInput.toLowerCase()
    for (const value in valueCounts) {
      if (!value.toLowerCase().includes(searchKey)) {
        delete valueCounts[value]
      }
    }
    return valueCounts
  }

  sortValueCount = () => {
    const valueCounts = this.props.valueCounts
    const items = Object.keys(valueCounts).map(key => {
      return [key, valueCounts[key]]
    })
    items.sort(function (a, b) {
      return b[1] - a[1]
    })
    const sortedValueCounts = {}
    for (const index in items) {
      const value = items[index][0]
      const count = items[index][1]
      sortedValueCounts[value] = count
    }
    return sortedValueCounts
  }

  /** Add/Remove from selectedValues and return when checked/unchecked **/
  onChangeIsSelected = (value, isSelected) => {
    let selectedValues = this.selectedValues
    if (isSelected) {
      selectedValues[value] = null
    } else {
      delete selectedValues[value]
    }
    this.onChange(selectedValues)
  }

  clearSelectedValues = () => {
    this.onChange({})
  }

  fillSelectedValues = () => {
    const valueCounts = this.props.valueCounts || {}
    let selectedValues = {}
    for (const value in valueCounts) {
      selectedValues[value] = null
    }
    this.onChange(selectedValues)
  }

  /** Used by react-virtualized to only render rows in module viewport **/
  renderRow = ({ key, index, isScrolling, isVisible, style }) => {
    const item = (
      <div key={key} style={style}>
        {this.valueComponentsRef[index]}
      </div>
    )
    return item
  }

  render () {
    const { searchInput } = this.state
    const selectedValues = this.selectedValues
    const valueCounts = this.props.valueCounts ? this.sortValueCount() : {}
    const canSearch = Object.keys(valueCounts).length > 1
    const isSearching = (searchInput !== '')
    const matchingValues = isSearching ? this.valueMatching(searchInput) : valueCounts

    // render only matching values
    const valueComponents = Object.keys(matchingValues).map(value => (
      <ValueItem
        key={value}
        name={value}
        count={matchingValues[value]}
        onChangeIsSelected={this.onChangeIsSelected}
        isSelected={(value in selectedValues)}
      />
    ))
    this.valueComponentsRef = valueComponents

    /** TODO: Hardcoded row heights and width for now for simplicity, in the future we'll need to implement:
     *  https://github.com/bvaughn/react-virtualized/blob/master/docs/CellMeasurer.md
     *
     *  Viewport capped at 10 items, if less than 10 height is adjusted accordingly
     */
    const rowHeight = 27.78
    const valueList = valueComponents.length > 0 ? (
      <List
        className={'react-list'}
        height={
          rowHeight * valueComponents.length > 300 ? 300 : rowHeight * valueComponents.length
        }
        width={246}
        rowCount={valueComponents.length}
        rowHeight={rowHeight}
        rowRenderer={this.renderRow}
        ref={(ref) => { this.valueListRef = ref }}
      />) : null

    return (
      <div className='value-parameter'>
        { !canSearch ? null : (
          <React.Fragment>
            <form className="in-module--search" onSubmit={this.onSubmit} onReset={this.onReset}>
              <input
                type='search'
                placeholder='Search values...'
                autoComplete='off'
                value={searchInput}
                onChange={this.onInputChange}
                onKeyDown={this.onKeyDown}
              />
              <button type="reset" className="close" title="Clear Search"><i className="icon-close"></i></button>
            </form>
            <AllNoneButtons
              isReadOnly={isSearching}
              clearSelectedValues={this.clearSelectedValues}
              fillSelectedValues={this.fillSelectedValues}
            />
          </React.Fragment>
        )}
        <ul className='value-groups'>
          {valueList}
        </ul>
        { (isSearching && canSearch && valueComponents.length === 0) ? (
          <div className='wf-module-error-msg'>No values</div>
        ) : null}
      </div>
    )
  }
}

export default withFetchedData(ValueSelect, 'valueCounts')
