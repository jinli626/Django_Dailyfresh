from django.contrib import admin
from django.utils.html import format_html

from .models import (
    GoodsType, Goods, GoodsSKU, GoodsImage,
    IndexGoodsBanner, IndexTypeGoodsBanner, IndexPromotionBanner
)


# 商品种类
@admin.register(GoodsType)
class GoodsTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'logo']
    search_fields = ['name']
    list_per_page = 20


# 商品SPU
@admin.register(Goods)
class GoodsAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    list_per_page = 20


# 商品SKU
@admin.register(GoodsSKU)
class GoodsSKUAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'type', 'price', 'stock', 'sales', 'status']
    list_filter = ['type', 'status']
    search_fields = ['name']
    list_per_page = 20


# 商品图片
@admin.register(GoodsImage)
class GoodsImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sku', 'image_tag']
    readonly_fields = ['image_tag']

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60" height="60" />', obj.image.url)
        return "-"

    image_tag.short_description = "预览图"


# 首页轮播商品
@admin.register(IndexGoodsBanner)
class IndexGoodsBannerAdmin(admin.ModelAdmin):
    list_display = ['id', 'sku', 'index']
    list_editable = ['index']
    list_per_page = 20


# 首页分类展示商品
@admin.register(IndexTypeGoodsBanner)
class IndexTypeGoodsBannerAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'sku', 'display_type', 'index']
    list_editable = ['display_type', 'index']
    list_per_page = 20


# 首页促销活动
@admin.register(IndexPromotionBanner)
class IndexPromotionBannerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'url', 'index']
    list_editable = ['index']
    search_fields = ['name']
    list_per_page = 20
