from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorCode, Problem
from apps.common.openapi import problem

from .models import Product
from .serializers import ProductSerializer, product_payload


class ProductCursorPagination(CursorPagination):
    page_size = 24
    max_page_size = 100
    page_size_query_param = "limit"
    ordering = ("name", "id")


class ProductListView(APIView):
    @extend_schema(
        operation_id="listProducts",
        summary="Browse the store's catalogue",
        parameters=[
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=False, description="Search by name or SKU."),
            OpenApiParameter(
                "kind", str, OpenApiParameter.QUERY, required=False, enum=["physical", "digital", "service"]
            ),
            OpenApiParameter("cursor", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: ProductSerializer(many=True)},
        tags=["Catalogue"],
    )
    def get(self, request):
        products = Product.objects.filter(is_active=True)
        query = request.query_params.get("q", "").strip()
        if query:
            products = products.filter(name__icontains=query) | products.filter(sku__iexact=query)
        kind = request.query_params.get("kind")
        if kind:
            products = products.filter(kind=kind)
        paginator = ProductCursorPagination()
        page = paginator.paginate_queryset(products, request, view=self)
        return paginator.get_paginated_response(ProductSerializer([product_payload(p) for p in page], many=True).data)


class ProductDetailView(APIView):
    @extend_schema(
        operation_id="getProduct",
        summary="Get one product",
        responses={200: ProductSerializer, 404: problem("Product not found in this store.")},
        tags=["Catalogue"],
    )
    def get(self, request, product_id):
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if product is None:
            raise Problem(404, ErrorCode.PRODUCT_NOT_FOUND, "Product not found in this store.")
        return Response(ProductSerializer(product_payload(product)).data)
