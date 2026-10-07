from django.db import connection
from django.http import JsonResponse


def health(request):
    """Comprueba que Django responde y que PostgreSQL esta accesible."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})
