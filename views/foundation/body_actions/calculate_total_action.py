class CalculateTotalAction:
    @staticmethod
    def execute(body_layout):
        total = 0.0
        for pid, selected in body_layout.product_manager.selected_products.items():
            if not selected:
                continue
            subtotal = body_layout.product_manager.get_product_subtotal(pid)
            if subtotal is not None:
                try:
                    total += float(subtotal or 0)
                except (TypeError, ValueError):
                    pass
                continue

            product = body_layout.product_service.get_product_by_id(pid)
            if product and "subtotal" in product:
                try:
                    total += float(product["subtotal"] or 0)
                except (TypeError, ValueError):
                    pass
        return total
