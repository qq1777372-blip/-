# RuoShop Admin UI Standards

## Page Structure

- Data pages use `DataTableShell` with `filters`, `toolbar`, default table, and `footer` slots.
- Pagination stays at the bottom of the available viewport and uses `ListPaginationFooter`.
- Desktop operation columns are fixed to the right and use a stable width.
- Mobile uses a compact list layout; do not squeeze desktop tables into the viewport.

## Tables

- Cell content is one line by default with ellipsis and a full-value tooltip/title.
- Sorting is performed by the API before pagination. UI sort events map to `sort_by` and `sort_order`.
- Default page size is 20. A page change must never change sorting or filters.
- Column visibility, order, and width share the same `TableHeaderManager` contract.
- Numeric columns align right; dates and statuses use stable widths.

## Visual Tokens

- Use variables prefixed with `--ui-`; do not introduce page-specific copies of common colors.
- Panel radius is 8px. Controls use 6px. Pills are reserved for status values.
- Page spacing follows the 4px scale: 4, 8, 12, 16, 20, 24, 32.
- Body text is 14px, secondary text 12px, section headings 18px.

## Interaction

- Icon buttons require a tooltip or accessible label.
- Destructive actions require confirmation and remain visually separated from primary actions.
- Loading, empty, error, and disabled states are required for every data view.
- Do not store passwords or authentication secrets in browser storage.
