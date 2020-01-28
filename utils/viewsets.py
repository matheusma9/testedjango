from drf_yasg import openapi


def list_response(viewset, model_serializer, qs, request):
    page = viewset.paginate_queryset(qs)
    if page is not None:
        serializer = model_serializer(
            page, many=True, context={"request": request})
        return viewset.get_paginated_response(serializer.data)
    serializer = model_serializer(qs, many=True)
    return Response(serializer.data)


def paginated_schema(schema):
    return openapi.Schema(type=openapi.TYPE_OBJECT, properties={
        'count': openapi.Schema(type=openapi.TYPE_INTEGER),
        'next': openapi.Schema(type=openapi.TYPE_STRING),
        'previous': openapi.Schema(type=openapi.TYPE_STRING),
        'total_pages': openapi.Schema(type=openapi.TYPE_INTEGER),
        'results': openapi.Schema(type=openapi.TYPE_ARRAY, items=schema)
    }
    )
