import frappe
def evidence_error():
    for r in frappe.get_all("Error Log", filters={"method": ["like", "%evidence%"]}, fields=["error"], order_by="creation desc", limit=1):
        print(r.error[-1500:])
