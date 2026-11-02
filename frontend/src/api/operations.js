export const PRODUCT_FIELDS = `
  id sku name category unitPriceMinor lowStockThreshold currentStock isLowStock
  createdAt updatedAt archivedAt
`;
export const MOVEMENT_FIELDS = `
  id productId productSku productName movementType quantityChange reason createdAt
`;
const RESULT_FIELDS = `product { ${PRODUCT_FIELDS} } errors { code field message }`;

export const DASHBOARD = `query Dashboard {
  dashboard { productCount totalUnits lowStockCount }
  products(filter: {lowStockOnly: true}, limit: 8) {
    items { ${PRODUCT_FIELDS} } totalCount
  }
}`;
export const PRODUCTS = `query Products($filter: ProductFilter!, $limit: Int!, $offset: Int!, $archiveStatus: ArchiveStatus!) {
  products(filter: $filter, limit: $limit, offset: $offset) { items { ${PRODUCT_FIELDS} } totalCount }
  categories(archiveStatus: $archiveStatus)
}`;
export const PRODUCT_DETAIL = `query ProductDetail($id: ID!, $limit: Int!, $offset: Int!) {
  product(id: $id) { ${PRODUCT_FIELDS} }
  stockMovements(filter: {productId: $id}, limit: $limit, offset: $offset) { items { ${MOVEMENT_FIELDS} } totalCount }
}`;
export const PRODUCT_EDITOR = `query ProductEditor($id: ID!) {
  product(id: $id) { ${PRODUCT_FIELDS} } categories
}`;
export const CATEGORIES = `query Categories { categories }`;
export const HISTORY = `query History($filter: MovementFilter!, $limit: Int!, $offset: Int!) {
  stockMovements(filter: $filter, limit: $limit, offset: $offset) { items { ${MOVEMENT_FIELDS} } totalCount }
}`;
export const CREATE_PRODUCT = `mutation CreateProduct($input: CreateProductInput!) {
  createProduct(input: $input) { ${RESULT_FIELDS} }
}`;
export const UPDATE_PRODUCT = `mutation UpdateProduct($input: UpdateProductInput!) {
  updateProduct(input: $input) { ${RESULT_FIELDS} }
}`;
export const RECEIVE_STOCK = `mutation ReceiveStock($input: StockInput!) {
  receiveStock(input: $input) { ${RESULT_FIELDS} }
}`;
export const ISSUE_STOCK = `mutation IssueStock($input: StockInput!) {
  issueStock(input: $input) { ${RESULT_FIELDS} }
}`;
export const ADJUST_STOCK = `mutation AdjustStock($input: AdjustmentInput!) {
  adjustStock(input: $input) { ${RESULT_FIELDS} }
}`;
export const ARCHIVE_PRODUCT = `mutation ArchiveProduct($id: ID!) {
  archiveProduct(id: $id) { ${RESULT_FIELDS} }
}`;
export const EXPORT_CSV = `query ExportCsv($filter: ProductFilter!) {
  inventoryCsv(filter: $filter) { filename contentType content }
}`;
