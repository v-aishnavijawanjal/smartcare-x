import csv
import io


def build_csv(headers, rows):
    """Build CSV content."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def csv_response(filename, headers, rows):
    """Return a CSV download response."""
    from flask import Response

    csv_data = build_csv(headers, rows)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )