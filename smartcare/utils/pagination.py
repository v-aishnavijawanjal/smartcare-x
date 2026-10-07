"""Pagination helpers."""

from flask import current_app, request

from smartcare.extensions import db


def paginate_query(query, page=None, per_page=None):
    page = page or request.args.get("page", 1, type=int)
    per_page = per_page or current_app.config.get("ITEMS_PER_PAGE", 10)

    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def pagination_summary(pagination):
    if pagination.total == 0:
        return "No results found"

    start = (pagination.page - 1) * pagination.per_page + 1
    end = min(pagination.page * pagination.per_page, pagination.total)
    return f"Showing {start}-{end} of {pagination.total} results"