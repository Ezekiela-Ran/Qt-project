from models.database_management import DatabaseManagement

class ProductsModel(DatabaseManagement):
    table_name = "products"
    name_column = "product_name"