from models.database_manager import DatabaseManager

class ProductService:
    def __init__(self):
        self.db = DatabaseManager()

    def get_products_by_type(self, type_id):
        return self.db.get_products_by_type(type_id)

    def get_max_ref_b_analyse(self):
        return self.db.get_max_ref_b_analyse()

    def allocate_next_ref_b_analyse(self):
        return self.db.allocate_next_ref_b_analyse()

    def get_product_by_id(self, product_id):
        return self.db.get_product_by_id(product_id)

    def add_product(self, type_id, name):
        return self.db.add_product(type_id, name)

    def is_num_act_unique(self, num_act, exclude_product_id=None):
        return self.db.is_num_act_unique(num_act, exclude_product_id=exclude_product_id)

    def update_product(self, pid, ref, num_act, physico, toxico, micro, subtotal, update_ref=True):
        # If update_ref is False, pass None for ref so DB method won't change it
        ref_value = ref if update_ref else None
        return self.db.update_product(pid, ref_value, num_act, physico, toxico, micro, subtotal)

    def delete_product(self, pid):
        return self.db.delete_product(pid)

    def insert_type(self, name):
        return self.db.insert_type(name)

    def delete_type(self, tid):
        return self.db.delete_type(tid)