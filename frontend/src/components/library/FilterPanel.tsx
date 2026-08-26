type Props = {
  dateFrom: string; setDateFrom: (value: string) => void;
  dateTo: string; setDateTo: (value: string) => void;
  minSize: string; setMinSize: (value: string) => void;
  orientation: string; setOrientation: (value: string) => void;
  sort: string; setSort: (value: string) => void;
  filterCount: number;
};

export function FilterPanel(props: Props) {
  const clear = () => {props.setDateFrom(''); props.setDateTo(''); props.setMinSize(''); props.setOrientation('any'); props.setSort('newest');};
  return <section className="filter-panel">
    <label>From<input type="date" value={props.dateFrom} onChange={event => props.setDateFrom(event.target.value)}/></label>
    <label>To<input type="date" value={props.dateTo} min={props.dateFrom} onChange={event => props.setDateTo(event.target.value)}/></label>
    <label>Minimum size<select value={props.minSize} onChange={event => props.setMinSize(event.target.value)}><option value="">Any size</option><option value="1">1 MB+</option><option value="5">5 MB+</option><option value="10">10 MB+</option><option value="25">25 MB+</option></select></label>
    <label>Orientation<select value={props.orientation} onChange={event => props.setOrientation(event.target.value)}><option value="any">Any orientation</option><option value="landscape">Landscape</option><option value="portrait">Portrait</option><option value="square">Square</option></select></label>
    <label>Sort by<select value={props.sort} onChange={event => props.setSort(event.target.value)}><option value="newest">Newest imported</option><option value="captured_desc">Newest captured</option><option value="captured_asc">Oldest captured</option><option value="size_desc">Largest files</option></select></label>
    <button disabled={!props.filterCount} onClick={clear}>Clear filters</button>
  </section>;
}
