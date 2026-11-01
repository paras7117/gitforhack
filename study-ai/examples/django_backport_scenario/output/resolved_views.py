# Conflicted Django ORM View during backport from main to stable/4.2.x
# Ticket: #34567 (Fixed outer join compiler regression)

from django.http import JsonResponse
from django.db.models import Q
from myapp.models import Order

def order_summary_view(request):
    user_id = request.GET.get("user_id")
    # Upstream main (PR #34567): Security and NULL outer join fix (Tested on main)
    orders = Order.objects.filter(Q(user_id=user_id) & ~Q(status="ARCHIVED")).select_related("customer", "invoice")
    return JsonResponse({"count": orders.count(), "orders": list(orders.values())})
