import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderReturn, OrderStatus, OrderType, PriceType
from app.models.product import Product, ProductVariant
from app.models.stock import Stock, BundleStock
from app.models.user import User, UserDistrict, UserTenant
from app.models.district import District
from app.models.states import State
from app.models.taluk import Taluk
from app.models.shop import Shop
from app.models.target import ExecutiveTarget, TargetType
from app.models.set_type import SetType
from app.models.category import Category
from app.models.role import Role


def _date_filters(query, model, date_from, date_to):
    if date_from:
        query = query.where(model.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(model.created_at <= datetime.combine(date_to, datetime.max.time()))
    return query


# ── Order Summary (dashboard-level) ───────────────────────────────────────────

async def get_order_summary(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    base = [Order.is_deleted == False, Order.parent_order_id == None]  # noqa
    if tenant_id:
        base.append(Order.tenant_id == tenant_id)
    if date_from:
        base.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        base.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    # Total orders and value
    total_q = await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*base)
    )
    total_count, total_value = total_q.one()

    # By status
    status_q = await db.execute(
        select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.status)
    )
    by_status = [
        {"status": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in status_q.all()
    ]

    # By type
    type_q = await db.execute(
        select(Order.order_type, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.order_type)
    )
    by_type = [
        {"orderType": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in type_q.all()
    ]

    # By price type
    price_q = await db.execute(
        select(Order.price_type, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.price_type)
    )
    by_price_type = [
        {"priceType": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in price_q.all()
    ]

    return {
        "totalOrders": total_count,
        "totalValue": float(total_value),
        "byStatus": by_status,
        "byType": by_type,
        "byPriceType": by_price_type,
    }


# ── Order Detail Report ────────────────────────────────────────────────────────

async def get_order_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    taluk_id: Optional[uuid.UUID] = None,
    shop_id: Optional[uuid.UUID] = None,
    distributor_id: Optional[uuid.UUID] = None,
    assigned_executive: Optional[uuid.UUID] = None,
    status: Optional[OrderStatus] = None,
    order_type: Optional[OrderType] = None,
) -> list[dict]:
    query = (
        select(Order)
        .where(Order.is_deleted == False, Order.parent_order_id == None)  # noqa
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.set_type),
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.shop),
            selectinload(Order.executive),
            selectinload(Order.distributor),
            selectinload(Order.tenant),
        )
    )

    query = _date_filters(query, Order, date_from, date_to)

    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
    if distributor_id:
        query = query.where(Order.distributor_id == distributor_id)
    if assigned_executive:
        query = query.where(Order.assigned_executive == assigned_executive)
    if status:
        query = query.where(Order.status == status)
    if order_type:
        query = query.where(Order.order_type == order_type)

    if district_id or taluk_id or state_id:
        query = query.join(Order.shop)
        if district_id:
            query = query.where(Shop.district_id == district_id)
        if taluk_id:
            query = query.where(Shop.taluk_id == taluk_id)
        if state_id:
            query = query.join(Shop.district).where(District.state_id == state_id)

    result = await db.execute(query.order_by(Order.created_at.desc()))
    orders = result.scalars().unique().all()

    rows = []
    for o in orders:
        for item in o.items:
            rows.append({
                "Order Number": o.order_number,
                "Date": o.created_at.strftime("%Y-%m-%d"),
                "Type": o.order_type.value,
                "Price Type": o.price_type.value,
                "Status": o.status.value,
                "Tenant": o.tenant.name if o.tenant else "",
                "Shop": o.shop.name if o.shop else "",
                "Executive": f"{o.executive.first_name} {o.executive.last_name}".strip() if o.executive else "",
                "Distributor": f"{o.distributor.first_name} {o.distributor.last_name}".strip() if o.distributor else "",
                "Product": item.product.name if item.product else "",
                "Variant Size": item.variant.size if item.variant else "",
                "Variant Color": item.variant.color if item.variant else "",
                "Set Type": item.set_type.name if item.set_type else "",
                "Count": item.count,
                "Unit Price": float(item.unit_price),
                "Total Price": float(item.total_price),
                "Subtotal": float(o.subtotal),
                "Discount %": float(o.discount_percent),
                "Discount Flat": float(o.discount_flat),
                "Discount Amount": float(o.discount_amount),
                "Total Amount": float(o.total_amount),
                "Stock Deducted": "Yes" if o.stock_deducted else "No",
                "Placed At": o.placed_at.strftime("%Y-%m-%d %H:%M") if o.placed_at else "",
                "Delivered At": o.delivered_at.strftime("%Y-%m-%d %H:%M") if o.delivered_at else "",
            })
    return rows


# ── Stock Report ───────────────────────────────────────────────────────────────

async def get_stock_report_data(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.stock)
            .selectinload(Stock.bundle_stocks)
            .selectinload(BundleStock.set_type),
        )
        .join(ProductVariant.product)
        .where(Product.is_deleted == False)
    )

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if product_id:
        query = query.where(ProductVariant.product_id == product_id)

    result = await db.execute(query)
    variants = result.scalars().all()

    rows = []
    for v in variants:
        stock = v.stock
        bundle_summary = ""
        if stock and stock.bundle_stocks:
            parts = [
                f"{bs.set_type.name if bs.set_type else 'Unknown'}:{bs.bundle_count}"
                for bs in stock.bundle_stocks
            ]
            bundle_summary = ", ".join(parts)

        rows.append({
            "Product": v.product.name if v.product else "",
            "SKU": v.sku or "",
            "Color": v.color or "",
            "Pattern": v.pattern or "",
            "Size": v.size or "",
            "Individual Stock": stock.individual_count if stock else 0,
            "Bundle Stocks": bundle_summary,
            "Status": "Active" if v.is_active else "Inactive",
        })
    return rows


async def get_stock_summary(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
) -> dict:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.stock).selectinload(Stock.bundle_stocks),
        )
        .join(ProductVariant.product)
        .where(Product.is_deleted == False)
    )
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    variants = result.scalars().all()

    total_individual = sum(v.stock.individual_count for v in variants if v.stock)
    out_of_stock = sum(1 for v in variants if v.stock and v.stock.individual_count == 0)
    low_stock = sum(1 for v in variants if v.stock and 0 < v.stock.individual_count <= 10)
    total_variants = len(variants)

    return {
        "totalVariants": total_variants,
        "totalIndividualStock": total_individual,
        "outOfStock": out_of_stock,
        "lowStock": low_stock,
        "inStock": total_variants - out_of_stock - low_stock,
    }


async def get_low_stock_report_data(
    db: AsyncSession,
    threshold: int = 10,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.stock),
        )
        .join(ProductVariant.product)
        .join(ProductVariant.stock)
        .where(Product.is_deleted == False, Stock.individual_count <= threshold)
    )

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    variants = result.scalars().all()

    rows = []
    for v in variants:
        rows.append({
            "Product": v.product.name if v.product else "",
            "SKU": v.sku or "",
            "Size": v.size or "",
            "Color": v.color or "",
            "Individual Stock": v.stock.individual_count if v.stock else 0,
            "Alert": "OUT OF STOCK" if v.stock and v.stock.individual_count == 0 else "LOW STOCK",
        })
    return rows


# ── Product Report ─────────────────────────────────────────────────────────────

async def get_product_report_data(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    query = (
        select(Product)
        .where(Product.is_deleted == False)
        .options(
            selectinload(Product.model_ref),
            selectinload(Product.variants).selectinload(ProductVariant.stock),
        )
    )
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    result = await db.execute(query)
    products = result.scalars().all()

    rows = []
    for p in products:
        active_variants = [v for v in p.variants if not v.is_deleted]
        total_individual = sum(
            v.stock.individual_count for v in active_variants if v.stock
        )

        # Order count and value for this product
        order_q = select(
            func.count(func.distinct(OrderItem.order_id)),
            func.coalesce(func.sum(OrderItem.total_price), 0)
        ).where(OrderItem.product_id == p.id)

        if date_from:
            order_q = order_q.join(Order, OrderItem.order_id == Order.id).where(
                Order.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to:
            order_q = order_q.join(Order, OrderItem.order_id == Order.id).where(
                Order.created_at <= datetime.combine(date_to, datetime.max.time())
            )

        order_count, order_value = (await db.execute(order_q)).one()

        rows.append({
            "Product": p.name,
            "Model": p.model_ref.name if p.model_ref else "",
            "Sell Type": p.sell_type.value,
            "DP Price": float(p.dp_price),
            "MRP": float(p.mrp),
            "Active Variants": len(active_variants),
            "Total Individual Stock": total_individual,
            "Total Orders": order_count,
            "Total Order Value (₹)": float(order_value),
            "Status": "Active" if p.is_active else "Inactive",
        })
    return rows


# ── Shop Report ────────────────────────────────────────────────────────────────

async def get_shop_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    taluk_id: Optional[uuid.UUID] = None,
    is_ebo: Optional[bool] = None,
) -> list[dict]:
    query = (
        select(Shop)
        .where(Shop.is_deleted == False)
        .options(
            selectinload(Shop.district).selectinload(District.state),
            selectinload(Shop.taluk),
        )
    )

    if district_id:
        query = query.where(Shop.district_id == district_id)
    if taluk_id:
        query = query.where(Shop.taluk_id == taluk_id)
    if is_ebo is not None:
        query = query.where(Shop.is_ebo == is_ebo)
    if state_id:
        query = query.join(Shop.district).where(District.state_id == state_id)

    result = await db.execute(query)
    shops = result.scalars().unique().all()

    rows = []
    for s in shops:
        order_q = (
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
            .where(
                Order.shop_id == s.id,
                Order.is_deleted == False,
                Order.parent_order_id == None,  # noqa
            )
        )
        order_q = _date_filters(order_q, Order, date_from, date_to)
        count, value = (await db.execute(order_q)).one()

        # Last order date
        last_order_q = await db.execute(
            select(func.max(Order.created_at)).where(
                Order.shop_id == s.id,
                Order.is_deleted == False,
            )
        )
        last_order_at = last_order_q.scalar()

        rows.append({
            "Shop": s.name,
            "Contact Person": s.contact_person or "",
            "Phone": s.contact_number or "",
            "District": s.district.name if s.district else "",
            "State": s.district.state.name if s.district and s.district.state else "",
            "Taluk": s.taluk.name if s.taluk else "",
            "EBO": "Yes" if s.is_ebo else "No",
            "Active": "Yes" if s.is_active else "No",
            "Total Orders": count,
            "Total Value (₹)": float(value),
            "Last Order Date": last_order_at.strftime("%Y-%m-%d") if last_order_at else "",
        })
    return rows


async def get_shop_summary(
    db: AsyncSession,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
) -> dict:
    query = select(func.count(Shop.id)).where(Shop.is_deleted == False)
    if district_id:
        query = query.where(Shop.district_id == district_id)
    if state_id:
        query = query.join(Shop.district).where(District.state_id == state_id)

    total = (await db.execute(query)).scalar() or 0
    ebo = (await db.execute(
        query.where(Shop.is_ebo == True)  # noqa
    )).scalar() or 0
    active = (await db.execute(
        query.where(Shop.is_active == True)  # noqa
    )).scalar() or 0

    return {
        "totalShops": total,
        "eboShops": ebo,
        "activeShops": active,
        "inactiveShops": total - active,
    }


# ── User Report ────────────────────────────────────────────────────────────────

async def get_user_report_data(
    db: AsyncSession,
    role_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
) -> list[dict]:
    from app.models.user import UserTenant

    query = (
        select(User)
        .where(User.is_deleted == False)
        .options(
            selectinload(User.role),
            selectinload(User.user_districts)
            .selectinload(UserDistrict.district)
            .selectinload(District.state),
            selectinload(User.user_tenants),
        )
    )

    if role_id:
        query = query.where(User.role_id == role_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if tenant_id:
        query = query.where(User.user_tenants.any(UserTenant.tenant_id == tenant_id))
    if district_id:
        query = query.where(User.user_districts.any(UserDistrict.district_id == district_id))
    if state_id:
        query = query.where(
            User.user_districts.any(
                UserDistrict.district_id.in_(
                    select(District.id).where(District.state_id == state_id)
                )
            )
        )

    result = await db.execute(query)
    users = result.scalars().unique().all()

    rows = []
    for u in users:
        districts = ", ".join([ud.district.name for ud in u.user_districts if ud.district])
        states = ", ".join(list(set([
            ud.district.state.name
            for ud in u.user_districts
            if ud.district and ud.district.state
        ])))
        rows.append({
            "Username": u.username,
            "First Name": u.first_name,
            "Last Name": u.last_name or "",
            "Email": u.email,
            "Phone": u.phone or "",
            "Role": u.role.name if u.role else "",
            "Districts": districts,
            "States": states,
            "Active": "Yes" if u.is_active else "No",
            "Verified": "Yes" if u.is_verified else "No",
            "Created": u.created_at.strftime("%Y-%m-%d"),
        })
    return rows


# ── Executive Performance Report ───────────────────────────────────────────────

async def get_executive_performance_data(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    exec_query = (
        select(User)
        .where(User.is_deleted == False, User.is_active == True)
        .join(User.role)
        .where(Role.name == "executive")
        .options(
            selectinload(User.user_districts)
            .selectinload(UserDistrict.district)
            .selectinload(District.state),
        )
    )

    if district_id:
        exec_query = exec_query.where(
            User.user_districts.any(UserDistrict.district_id == district_id)
        )
    if state_id:
        exec_query = exec_query.where(
            User.user_districts.any(
                UserDistrict.district_id.in_(
                    select(District.id).where(District.state_id == state_id)
                )
            )
        )

    exec_result = await db.execute(exec_query)
    executives = exec_result.scalars().unique().all()

    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]
    rows = []

    for exe in executives:
        base_filters = [
            Order.assigned_executive == exe.id,
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        ]

        order_count = (await db.execute(
            select(func.count(Order.id)).where(*base_filters)
        )).scalar() or 0

        order_value = float((await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(*base_filters)
        )).scalar() or 0)

        # By status breakdown
        status_q = await db.execute(
            select(Order.status, func.count(Order.id))
            .where(*base_filters)
            .group_by(Order.status)
        )
        status_breakdown = {row[0].value: row[1] for row in status_q.all()}

        # Delivered orders
        delivered_count = (await db.execute(
            select(func.count(Order.id)).where(
                Order.assigned_executive == exe.id,
                Order.is_deleted == False,
                Order.status == OrderStatus.delivered,
                Order.parent_order_id == None,  # noqa
                extract("year", Order.created_at) == year,
                extract("month", Order.created_at) == month,
            )
        )).scalar() or 0

        # Targets
        targets = (await db.execute(
            select(ExecutiveTarget).where(
                ExecutiveTarget.user_id == exe.id,
                ExecutiveTarget.year == year,
                ExecutiveTarget.month == month,
            )
        )).scalars().all()

        target_map = {t.target_type: float(t.target_value) for t in targets}
        count_target = target_map.get(TargetType.order_count, 0)
        value_target = target_map.get(TargetType.order_value, 0)

        districts = ", ".join([ud.district.name for ud in exe.user_districts if ud.district])

        rows.append({
            "Executive": f"{exe.first_name} {exe.last_name}".strip(),
            "Username": exe.username,
            "Phone": exe.phone or "",
            "Districts": districts,
            "Total Orders": order_count,
            "Delivered Orders": delivered_count,
            "Delivery Rate %": round((delivered_count / order_count * 100), 2) if order_count else 0,
            "Order Count Target": count_target,
            "Count Achievement %": round((order_count / count_target * 100), 2) if count_target else "N/A",
            "Order Value (₹)": order_value,
            "Value Target (₹)": value_target,
            "Value Achievement %": round((order_value / value_target * 100), 2) if value_target else "N/A",
            **{f"Status - {k}": v for k, v in status_breakdown.items()},
        })

    return rows


async def get_executive_summary(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
) -> dict:
    exec_count = (await db.execute(
        select(func.count(User.id))
        .where(User.is_deleted == False, User.is_active == True)
        .join(User.role)
        .where(Role.name == "executive")
    )).scalar() or 0

    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    total_orders = (await db.execute(
        select(func.count(Order.id)).where(
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        )
    )).scalar() or 0

    total_value = float((await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        )
    )).scalar() or 0)

    return {
        "year": year,
        "month": month,
        "totalExecutives": exec_count,
        "totalOrders": total_orders,
        "totalOrderValue": total_value,
        "averageOrdersPerExecutive": round(total_orders / exec_count, 2) if exec_count else 0,
        "averageValuePerExecutive": round(total_value / exec_count, 2) if exec_count else 0,
    }


# ── Distributor Report ─────────────────────────────────────────────────────────

async def get_distributor_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    dist_query = (
        select(User)
        .where(User.is_deleted == False)
        .join(User.role)
        .where(Role.name == "distributor")
        .options(
            selectinload(User.user_districts).selectinload(UserDistrict.district),
        )
    )

    if district_id:
        dist_query = dist_query.where(
            User.user_districts.any(UserDistrict.district_id == district_id)
        )

    dist_result = await db.execute(dist_query)
    distributors = dist_result.scalars().unique().all()

    rows = []
    for d in distributors:
        base = [
            Order.distributor_id == d.id,
            Order.is_deleted == False,
            Order.parent_order_id == None,  # noqa
        ]
        if date_from:
            base.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            base.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

        count, value = (await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*base)
        )).one()

        delivered = (await db.execute(
            select(func.count(Order.id)).where(
                *base, Order.status == OrderStatus.delivered
            )
        )).scalar() or 0

        rejected = (await db.execute(
            select(func.count(Order.id)).where(
                *base, Order.status == OrderStatus.rejected
            )
        )).scalar() or 0

        districts = ", ".join([ud.district.name for ud in d.user_districts if ud.district])

        rows.append({
            "Distributor": f"{d.first_name} {d.last_name}".strip(),
            "Username": d.username,
            "Phone": d.phone or "",
            "Districts": districts,
            "Total Orders": count,
            "Delivered": delivered,
            "Rejected": rejected,
            "Total Value (₹)": float(value),
            "Delivery Rate %": round((delivered / count * 100), 2) if count else 0,
        })

    return rows


# ── Returns Report ─────────────────────────────────────────────────────────────

async def get_returns_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(OrderReturn)
        .options(
            selectinload(OrderReturn.order),
            selectinload(OrderReturn.product),
            selectinload(OrderReturn.variant),
            selectinload(OrderReturn.set_type),
            selectinload(OrderReturn.processor),
        )
    )

    if date_from:
        query = query.where(OrderReturn.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(OrderReturn.created_at <= datetime.combine(date_to, datetime.max.time()))
    if product_id:
        query = query.where(OrderReturn.product_id == product_id)

    result = await db.execute(query.order_by(OrderReturn.created_at.desc()))
    returns = result.scalars().all()

    rows = []
    for r in returns:
        rows.append({
            "Date": r.created_at.strftime("%Y-%m-%d"),
            "Order Number": r.order.order_number if r.order else "",
            "Product": r.product.name if r.product else "",
            "Variant Size": r.variant.size if r.variant else "",
            "Variant Color": r.variant.color if r.variant else "",
            "Set Type": r.set_type.name if r.set_type else "",
            "Return Type": r.return_type.value,
            "Count": r.count,
            "Processed By": f"{r.processor.first_name} {r.processor.last_name}".strip() if r.processor else "",
            "Notes": r.notes or "",
        })
    return rows