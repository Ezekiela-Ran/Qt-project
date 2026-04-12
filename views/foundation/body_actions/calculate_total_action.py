class CalculateTotalAction:
    @staticmethod
    def execute(body_layout):
        total = 0.0
        for line_item in body_layout.product_manager.get_preview_line_items():
            pid = line_item.get("product_id")
            product = body_layout.product_service.get_product_by_id(pid)
            if product and "subtotal" in product:
                try:
                    quantity = max(int(line_item.get("quantity") or 1), 1)
                    total += float(product["subtotal"] or 0) * quantity
                except (TypeError, ValueError):
                    pass
        return total
