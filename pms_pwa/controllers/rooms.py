import datetime

from odoo import _, http
from odoo.http import request


class Rooms(http.Controller):
    @http.route(
        "/rooms",
        type="json",
        website=True,
        auth="public",
    )
    def list_available_rooms(self):
        rooms = []

        payload = http.request.jsonrequest.get("params")

        checkin = payload["checkin"]
        checkin = datetime.datetime.strptime(checkin, '%Y-%m-%d')

        checkout = payload['checkout']
        checkout = datetime.datetime.strptime(checkout, '%Y-%m-%d')

        pms_property_id = int(payload['pms_property_id'])
        pricelist_id = int(payload['pricelist_id'])

        reservation_id = int(payload['reservation_id'])

        reservation = (
            request.env["pms.reservation"].sudo().search([("id", "=", int(reservation_id))])
        )
        if not reservation:
            reservation_line_ids = False
        else:
            reservation_line_ids = reservation.reservation_line_ids.ids

        rooms_avail = request.env['pms.room.type.availability.plan'].sudo().rooms_available(
            checkin=checkin,
            checkout=checkout,
            current_lines=reservation_line_ids,
            pricelist_id=pricelist_id,
            pms_property_id=pms_property_id,
        )

        pms = request.env["pms.room.type"].sudo().search([])

        for room in rooms_avail:
            rooms.append(
                {
                    "id": room.id,
                    "name": room.name
                }
            )

        return rooms
