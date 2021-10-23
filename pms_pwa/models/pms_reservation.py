# Copyright 2017  Dario Lodeiros
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime
import json
import logging
import pprint

import avinit

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import get_lang

from ..controllers import controller_room_types, controller_rooms

pp = pprint.PrettyPrinter(indent=4)


_logger = logging.getLogger(__name__)


class PmsReservation(models.Model):
    _inherit = "pms.reservation"

    # REVIEW:store = true? (pwa_action_buttons & pwa_board_service_tags)
    pwa_action_buttons = fields.Char(compute="_compute_pwa_action_buttons")
    pwa_board_service_tags = fields.Char(compute="_compute_pwa_board_service_tags")
    partner_image_128 = fields.Image(
        string="Image",
        help="Partner Image, it corresponds with Partner Image associated or name initials",
        store=True,
        compute="_compute_partner_image_128",
    )
    image_autogenerated = fields.Boolean(
        string="Autogenerate image",
        help="Indicates if the image was auto-generated to overwrite if renamed",
        compute_sudo=True,
        default=False,
    )
    color_state = fields.Char(
        string="Color state",
        help="Define state to color in PWA",
        compute="_compute_color_state",
        store=True,
    )
    icon_payment = fields.Char(
        string="Icon Payment state",
        help="Define payment to icon in PWA",
        compute="_compute_icon_payment",
    )

    def _compute_pwa_board_service_tags(self):
        for record in self:
            board_service_tags = list()
            for service in record.service_ids:
                if service.is_board_service:
                    board_service_tags.append(service.name)
            record.pwa_board_service_tags = json.dumps(board_service_tags)

    def _compute_pwa_action_buttons(self):
        """Return ordered button list, where the first button is
        the preditive action, the next are active actions:
        - "Assign":     Predictive: Reservation by assign
                        Active- Idem
        - "checkin":    Predictive- state 'confirm' and checkin day
                        Active- Idem and assign
        - "checkout":   Predictive- Pay, onboard and checkout day
                        Active- Onboard and checkout day
        - "Pay":        Predictive- Onboard and pending amount > 0
                        Active- pending amount > 0
        - "Invoice":    Predictive- qty invoice > 0, onboard, pending amount = 0
                        Active- qty invoice > 0
        - "Cancel":     Predictive- Never
                        Active- state in draft, confirm, onboard, full onboard
        """
        buttons = {
            "Asignar": "/assign",
            "Checkins": "/checkin",
            "Checkout": "/checkout",
            "Pagar": "/payment",
            "Facturar": "/invoice",
            "Cancelar": "/cancel",
        }
        for reservation in self:
            active_buttons = {}
            for k, v in buttons.items():
                if v == "/assign":
                    if reservation.to_assign:
                        active_buttons[k] = "/reservation/" + str(reservation.id) + v
                    else:
                        active_buttons[k] = False
                elif v == "/checkin":
                    active_buttons[k] = "/reservation/" + str(reservation.id) + v
                elif v == "/checkout":
                    if reservation.allowed_checkout:
                        active_buttons[k] = "/reservation/" + str(reservation.id) + v
                    else:
                        active_buttons[k] = False
                elif v == "/payment":
                    if reservation.folio_pending_amount > 0:
                        active_buttons[k] = "/reservation/" + str(reservation.id) + v
                    else:
                        active_buttons[k] = False
                elif v == "/invoice":
                    if reservation.invoice_status == "to invoice":
                        active_buttons[k] = "/reservation/" + str(reservation.id) + v
                    else:
                        active_buttons[k] = False
                elif v == "/cancel":
                    if reservation.allowed_cancel:
                        active_buttons[k] = "/reservation/" + str(reservation.id) + v
                    else:
                        active_buttons[k] = False
            if all(not v for k, v in active_buttons.items()):
                active_buttons["Ver Detalle"] = "/reservation/" + str(reservation.id)

            reservation.pwa_action_buttons = json.dumps(active_buttons)

    @api.depends("partner_id", "partner_id.image_128", "partner_name")
    def _compute_partner_image_128(self):
        for record in self:
            if record.partner_id:
                record.partner_image_128 = record.partner_id.image_128
            elif record.partner_name and (
                not record.partner_image_128 or record.image_autogenerated
            ):
                avatar = avinit.get_avatar_data_url(record.partner_name)
                record.partner_image_128 = avatar[26:]
                _logger.info(record.partner_image_128)
            elif not record.partner_image_128:
                record.partner_image_128 = False

    @api.model
    def pwa_action_checkin(
        self, checkin_partner_list, reservation_id, action_on_board=False
    ):
        try:
            reservation = self.browse(reservation_id)
            if reservation:
                if len(checkin_partner_list) > reservation.adults:
                    raise ValidationError(
                        _("The list of guests is greater than the capacity")
                    )
                for guest in checkin_partner_list:
                    if guest.get("document_type"):
                        guest["document_type"] = (
                            self.env["res.partner.id_category"]
                            .search([("code", "=", guest["document_type"])])
                            .id
                        )
                    # REVIEW: avoid send "false" to controller
                    if guest.get("country_id") and guest.get("country_id") != "false":
                        guest["nationality_id"] = int(guest["country_id"])
                    guest.pop("country_id")

                    # REVIEW: avoid send "false" to controller
                    if guest.get("state_id") == "false":
                        guest.pop("state_id")
                    elif guest.get("state_id"):
                        guest["state_id"] = int(guest["state_id"])

                    if guest.get("birthdate_date"):
                        guest["birthdate_date"] = datetime.datetime.strptime(
                            guest["birthdate_date"], get_lang(self.env).date_format
                        ).date()

                    if guest.get("document_expedition_date"):
                        guest["document_expedition_date"] = datetime.datetime.strptime(
                            guest["document_expedition_date"],
                            get_lang(self.env).date_format,
                        ).date()

                    checkin_partner = self.env["pms.checkin.partner"].browse(
                        int(guest["id"])
                    )
                    guest.pop("id")
                    if guest.get("pms_property_id"):
                        guest.pop("pms_property_id")

                    vals = {}
                    for checkin_field in guest:
                        relational = checkin_partner._fields[checkin_field].relational
                        record_value = checkin_partner[checkin_field]
                        if relational:
                            record_value = record_value.id
                        if (
                            guest.get(checkin_field)
                            and guest.get(checkin_field) != record_value
                        ):
                            vals[checkin_field] = guest[checkin_field]
                    # pprint(vals)
                    if len(vals) >= 1:
                        checkin_partner.write(vals)
                    if action_on_board:
                        checkin_partner.action_on_board()
            return True
        except Exception as e:
            _logger.error(e)
            return json.dumps({"result": False, "message": str(e)})

    def _get_reservation_services(self):
        # REVIEW: Is not Used??
        """
        @return: Return dict with services,
        if normal service return only qty, if service per day
         return subdict with dates and qty per date
         {
            'service_per_day_id': {
                'name': 'service name',
                'lines': [
                    {"date": date, "qty": product_qty},
                    {"date": date, "qty": product_qty},
                    ]
                },
            'service_normal_id': {
                'name': 'service name',
                'qty': product_qty
                },
            'service_per_day_id': {
                'name': 'service name',
                'lines': [
                    {"date": date, "qty": product_qty},
                    {"date": date, "qty": product_qty},
                    ]
                },
         }
        """
        self.ensure_one()
        reservation_extra = {}
        for service in self.service_ids:
            if service.per_day:
                reservation_extra[service.id] = {}
                reservation_extra[service.id]["name"] = service.name
                lines = []
                for line in service.service_line_ids:
                    lines.append(
                        {
                            "date": line.date.strftime(get_lang(self.env).date_format),
                            "day_qty": line.day_qty,
                            "price_unit": line.price_unit,
                        }
                    )
                reservation_extra[service.id]["lines"] = lines
            else:
                reservation_extra[service.id] = {
                    "name": service.name,
                    "product_qty": service.product_qty,
                }
        return reservation_extra

    def _get_checkin_partner_ids(self):
        """
        @return: Return dict with checkin_partner_ids
         [
          id: {"name": name, "mobile": mobile, "email": email},
          id: {"name": name, "mobile": mobile, "email": email},
          ...
          id: {"name": name, "mobile": mobile, "email": email},
         ]
        """
        self.ensure_one()
        checkin_partners = {}

        for checkin in self.checkin_partner_ids:
            allowed_states = [{"id": False, "name": ""}]
            if checkin.nationality_id:
                for state in self.env["res.country.state"].search(
                    [("country_id", "=", checkin.nationality_id.id)]
                ):
                    allowed_states.append(
                        {
                            "id": state.id,
                            "name": state.name,
                        }
                    )
            checkin_partners[checkin.id] = {
                "id": checkin.id,
                "partner_id": checkin.partner_id.id if checkin.partner_id else None,
                "firstname": checkin.firstname,
                "lastname": checkin.lastname,
                "lastname2": checkin.lastname2,
                "birthdate_date": checkin.birthdate_date.strftime(
                    get_lang(self.env).date_format
                )
                if checkin.birthdate_date
                else False,
                "document_number": checkin.document_number,
                "document_expedition_date": checkin.document_expedition_date.strftime(
                    get_lang(self.env).date_format
                )
                if checkin.document_expedition_date
                else False,
                "document_type": checkin.document_type.code,
                "mobile": checkin.mobile,
                "email": checkin.email,
                "gender": checkin.gender,
                "state_id": {
                    "id": checkin.state_id.id if checkin.state_id else False,
                    "name": checkin.state_id.name if checkin.state_id else "",
                },
                "state_name": checkin.state_id.display_name
                if checkin.state_id
                else None,
                "country_id": {
                    "id": checkin.nationality_id.id
                    if checkin.nationality_id
                    else False,
                    "name": checkin.nationality_id.name
                    if checkin.nationality_id
                    else "",
                },
                "country_name": checkin.nationality_id.display_name
                if checkin.nationality_id
                else None,
                "allowed_state_ids": allowed_states,
                "state": checkin.state or False,
                "readonly_fields": self._get_checkin_read_only_fields(checkin),
                "invisible_fields": self._get_checkin_invisible_fields(checkin),
            }
        return checkin_partners

    def _get_service_ids(self):
        """
        @return: Return dict with service_ids
         [
          id: {"name": "productname", "service_line_ids": service_line_ids},
          id: {"name": "productname", "service_line_ids": service_line_ids},
          ...
          id: {"name": "productname", "service_line_ids": service_line_ids},
         ]
        """
        self.ensure_one()
        service_ids = {}
        for service in self.service_ids:
            service_ids[service.id] = {
                "product_id": service.product_id.name,
                "service_line_ids": service._get_service_line_ids(),
            }

        return service_ids

    def _get_reservation_line_ids(self):
        """
        @return: Return dict with nights, price, discount
         {
          id: {"date": date, "price": price, "discount": discount},
          id: {"date": date, "price": price, "discount": discount},
          ...
          id: {"date": date, "price": price, "discount": discount},
         }
        """
        self.ensure_one()
        reservation_lines = {}
        for line in self.reservation_line_ids:
            reservation_lines[line.id] = {
                "date": line.date.strftime(get_lang(self.env).date_format),
                "price": line.price,
                "discount": line.discount,
            }
            # TODO: Splitted Reservations has different rooms at line
            # TODO: Cancel Discount, calculate on discount or send separately??)
        return reservation_lines

    def _get_allowed_board_service_room_ids(self):
        self.ensure_one()
        allowed_board_services = self.env[
            "pms.room.type"
        ]._get_allowed_board_service_room_ids(
            room_type_id=self.room_type_id.id,
            pms_property_id=self.pms_property_id.id,
        )
        if not any(
            item["id"] == self.board_service_room_id.id
            for item in allowed_board_services
        ):
            allowed_board_services.append(
                {
                    "id": self.board_service_room_id.pms_board_service_id.id,
                    "name": self.board_service_room_id.pms_board_service_id.name
                    if self.board_service_room_id
                    else "",
                }
            )
        return allowed_board_services or False

    def _get_allowed_service_ids(self):
        self.ensure_one()
        services = self.env["product.product"].search(
            [
                ("sale_ok", "=", True),
                "|",
                ("pms_property_ids", "=", False),
                ("pms_property_ids", "in", self.pms_property_id.id),
            ]
        )
        allowed_services = [
            {
                "id": False,
                "name": "",
            }
        ]
        for service in services:
            allowed_services.append(
                {
                    "id": service.id,
                    "name": service.name,
                }
            )
        return allowed_services

    @api.model
    def _get_allowed_extras(self, partner=False, pricelist=False):
        # REVIEW: Is not used?
        """
        @return: Return dict with list main extras and secondary extras
        {
             main_extras: [
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
             ]
             secondary_extras: [
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
                ...
                {'id': id, 'name': name, 'per_day': Boolean, 'unit_price': Float}
             ]
        }
        """
        products = self.env["product.product"].search(
            [
                ("sale_ok", "=", True),
                ("id", "not in", self.env["pms.room.type"].mapped("product_id.id")),
            ]
        )
        # TODO: Sort product by sales count (compute field on product?)
        allowed_extras = {"main_extras": [], "secondary_extras": []}
        max_main_extras = 3
        main_count_extras = 0
        for product in products:
            product = product.with_context(
                lang=partner.lang,
                partner=partner.id,
                quantity=1,
                date=fields.Date.today(),
                # TODO: Pricelist default on property
                pricelist=pricelist
                or self.env["product.pricelist"].search(
                    [
                        "|",
                        ("company_id", "=", False),
                        ("company_id", "=", self.env.company.id),
                    ],
                    limit=1,
                ),
                uom=product.uom_id.id,
                # TODO: Property -to pricelist property rules-
            )
            if main_count_extras <= max_main_extras:
                main_count_extras += 1
                allowed_extras["main_extras"].append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "per_day": product.per_day,
                        "unit_price": product.price,
                    }
                )
            else:
                allowed_extras["secondary_extras"].append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "per_day": product.per_day,
                        "unit_price": product.price,
                    }
                )
        return allowed_extras

    @api.model
    def _get_allowed_pricelists(self, pms_property_ids, channel_type_id=False):
        pricelists = self.env["product.pricelist"].search(
            [
                "|",
                ("pms_sale_channel_ids", "=", False),
                (
                    "pms_sale_channel_ids",
                    "in",
                    channel_type_id if channel_type_id else [],
                ),
                "|",
                ("pms_property_ids", "=", False),
                ("pms_property_ids", "in", pms_property_ids),
            ]
        )
        allowed_pricelists = []
        for pricelist in pricelists:
            if not pricelist.pms_sale_channel_ids or any(
                not channel.is_on_line for channel in pricelist.pms_sale_channel_ids
            ):
                allowed_pricelists.append(
                    {
                        "id": pricelist.id,
                        "name": pricelist.display_name,
                    }
                )
        return allowed_pricelists

    @api.model
    def _get_allowed_segmentations(self):
        segmentations = self.env["res.partner.category"].search([])
        allowed_segmentations = []
        for tag in segmentations:
            if tag.display_name not in [item["name"] for item in allowed_segmentations]:
                allowed_segmentations.append(
                    {
                        "id": tag.id,
                        "name": tag.display_name,
                    }
                )
        return allowed_segmentations

    @api.depends("state", "reservation_type", "folio_pending_amount", "to_assign")
    def _compute_color_state(self):
        for record in self:
            if record.to_assign:
                record.color_state = "to-assign"
            elif record.reservation_type == "out":
                record.color_state = "out-service"
            elif record.reservation_type == "staff":
                record.color_state = "staff"
            elif record.state == "draft":
                record.color_state = "prereservation"
            elif record.state in ("confirm", "arrival_delayed"):
                record.color_state = "confirmed"
            elif record.state in ("onboard", "departure_delayed"):
                record.color_state = "onboard"
                if record.folio_pending_amount > 0:
                    record.color_state = "checkin-to-pay"
                else:
                    record.color_state = "checkin-paid"
            elif record.state == "done":
                if record.folio_pending_amount > 0:
                    record.color_state = "checkout-to-pay"
                else:
                    record.color_state = "checkout-paid"
            else:
                record.color_state = False

    def _compute_icon_payment(self):
        for record in self:
            if record.folio_payment_state == "paid":
                record.icon_payment = "paid"
            else:
                record.icon_payment = "pending"

    @api.model
    def _get_reservation_types(self):
        return [
            {"id": "out", "name": "Out of service"},
            {"id": "normal", "name": "Normal"},
            {"id": "staff", "name": "Staff"},
        ]

    def parse_reservation(self):
        self.ensure_one()
        primary_button, secondary_buttons = self.generate_reservation_style_buttons()

        if self.partner_id:
            partner_vals = {
                "id": self.partner_id.id,
                "name": self.partner_id.name if self.partner_name else "",
                "mobile": self.partner_id.mobile or self.partner_id.phone,
            }
        else:
            partner_vals = {
                "id": False,
                "name": self.partner_name if self.partner_name else "",
                "mobile": self.mobile,
            }
        notifications = []
        if self.partner_internal_comment:
            notifications.append(
                {
                    "title": "Notas sobre Cliente",
                    "content": self.partner_internal_comment,
                }
            )
        if self.folio_internal_comment:
            notifications.append(
                {
                    "title": "Notas sobre Reserva",
                    "content": self.folio_internal_comment,
                }
            )
        if self.partner_requests:
            notifications.append(
                {
                    "title": "Peticiones de Cliente",
                    "content": self.partner_requests,
                }
            )

        readonly_fields = self._get_reservation_read_only_fields()

        # avoid send o2m & m2m fields on new single reservation modal
        reservation_line_ids = (
            self._get_reservation_line_ids() if isinstance(self.id, int) else False
        )
        service_ids = self._get_service_ids() if isinstance(self.id, int) else False
        checkin_partner_ids = (
            self._get_checkin_partner_ids() if isinstance(self.id, int) else False
        )

        reservation_values = dict()

        reservation_values = {
            "id": self.id,
            "current_ubication_id": self.preferred_room_id.ubication_id.id,
            "current_room_type_id": self.preferred_room_id.room_type_id.id,
            "current_property_id": self.pms_property_id.id,
            "name": self.name if self.name else "",
            "splitted": self.splitted,
            "partner_id": partner_vals,
            "unread_msg": len(notifications),
            "messages": notifications,
            "folio_reservations": self.folio_id.get_reservation_json(),
            "folio_reservations_count": len(self.folio_id.reservation_ids),
            "room_type_id": {
                "id": self.room_type_id.id,
                "name": self.room_type_id.name,
                "default_code": self.room_type_id.default_code,
            },
            "preferred_room_id": {
                "id": self.preferred_room_id.id if self.preferred_room_id else False,
                "name": self.rooms if self.rooms else "",
            },
            "channel_type_id": {
                "id": self.channel_type_id.id if self.channel_type_id else False,
                "name": self.channel_type_id.name if self.channel_type_id else "",
            },
            "agency_id": {
                "id": self.agency_id.id if self.agency_id else False,
                "name": self.agency_id.name if self.agency_id else False,
                "url": self.env["website"].image_url(self.agency_id, "image_128")
                if self.agency_id
                else False,
            },
            "user_name": self.user_id.name if self.user_id else False,
            "nights": self.nights,
            "checkin": self.checkin.strftime(get_lang(self.env).date_format),
            "arrival_hour": self.arrival_hour,
            "checkout": self.checkout.strftime(get_lang(self.env).date_format),
            "departure_hour": self.departure_hour,
            "folio_id": {
                "id": self.folio_id.id,
                "amount_total": round(self.folio_id.amount_total, 2),
                "outstanding_vat": round(self.folio_pending_amount, 2),
            },
            "state": self.state,
            "credit_card_details": self.credit_card_details,
            "price_total": round(self.price_room_services_set, 2),
            "price_tax": round(self.price_tax, 2),
            "folio_pending_amount": round(self.folio_pending_amount, 2),
            "folio_internal_comment": self.folio_internal_comment,
            "payment_methods": self.pms_property_id._get_allowed_payments_journals(),
            "reservation_types": self._get_reservation_types(),
            "reservation_type": self.reservation_type,
            "checkins_ratio": self.checkins_ratio,
            "ratio_checkin_data": self.ratio_checkin_data,
            "adults": self.adults,
            "checkin_partner_ids": checkin_partner_ids,
            "pms_property_id": {
                "id": self.pms_property_id.id,
                "name": self.pms_property_id.display_name,
            },
            "service_ids": service_ids,
            "reservation_line_ids": reservation_line_ids,
            "allowed_board_service_room_ids": self._get_allowed_board_service_room_ids(),
            "board_service_room_id": {
                "id": self.board_service_room_id.id
                if self.board_service_room_id
                else False,
                "name": self.board_service_room_id.pms_board_service_id.name
                if self.board_service_room_id
                else "",
            },
            "allowed_service_ids": self._get_allowed_service_ids(),
            "primary_button": primary_button,
            "secondary_buttons": secondary_buttons,
            "pricelist_id": {
                "id": self.pricelist_id.id if self.pricelist_id else False,
                "name": self.pricelist_id.name if self.pricelist_id else "",
            },
            "allowed_pricelists": self._get_allowed_pricelists(
                [self.pms_property_id.id], self.channel_type_id.id
            ),
            "allowed_segmentations": self._get_allowed_segmentations(),
            "allowed_channel_type_ids": self.pms_property_id._get_allowed_channel_type_ids(),
            "allowed_agency_ids": self.pms_property_id._get_allowed_agency_ids(
                channel_type_id=self.channel_type_id.id
                if self.channel_type_id
                else False
            ),
            "segmentation_ids": self.segmentation_ids.ids,
            "room_numbers": controller_rooms.Rooms._get_available_rooms(
                self=self,
                payload={
                    "pms_property_id": self.pms_property_id.id,
                    "pricelist_id": self.pricelist_id.id,
                    "checkin": self.checkin,
                    "checkout": self.checkout,
                    "reservation_id": self.id,
                    "room_type_id": self.room_type_id,
                },
            ),
            "room_types": controller_room_types.RoomTypes._get_available_room_types(
                self=self,
                payload={
                    "pms_property_id": self.pms_property_id.id,
                    "pricelist_id": self.pricelist_id.id,
                    "checkin": self.checkin,
                    "checkout": self.checkout,
                    "reservation_id": self.id,
                },
            ),
            "readonly_fields": readonly_fields,
            "required_fields": [],
            "allowed_country_ids": self.pms_property_id._get_allowed_countries(),
        }

        _logger.info("Values from controller to Frontend:")
        pp.pprint(reservation_values)
        return reservation_values

    def generate_reservation_style_buttons(self):
        self.ensure_one()
        buttons = json.loads(self.pwa_action_buttons)
        keys = buttons.keys()
        keysList = [key for key in keys]

        primary_button = ""
        secondary_buttons = ""

        counter = 0
        primary = 0
        for _key in keysList:
            if (primary == 0 and buttons[keysList[counter]]) or keysList[
                counter
            ] == "Ver Detalle":
                if buttons[keysList[counter]]:
                    primary_button = (
                        "<button url='"
                        + buttons[keysList[counter]]
                        + "' data-id='"
                        + str(self.id)
                        + "' class='btn o_pms_pwa_default_button_name"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
                    primary = 1
                else:
                    primary_button = (
                        "<button"
                        + " class='disabled btn o_pms_pwa_default_button_name"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' data-id='"
                        + str(self.id)
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
            else:
                if buttons[keysList[counter]]:
                    secondary_buttons += (
                        "<button url='"
                        + buttons[keysList[counter]]
                        + "' class='dropdown-item  o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' data-id='"
                        + str(self.id)
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
                else:
                    secondary_buttons += (
                        "<button class='disabled dropdown-item"
                        + " o_pms_pwa_abutton o_pms_pwa_button_"
                        + str(keysList[counter].lower())
                        + "' data-id='"
                        + str(self.id)
                        + "' type='button'>"
                        + keysList[counter]
                        + "</button>"
                    )
            counter += 1
        return (primary_button, secondary_buttons)

    def get_json(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "preferred_room_id": {
                "id": self.preferred_room_id.id if self.preferred_room_id else False,
                "name": self.rooms if self.rooms else "",
            },
            "room_numbers": controller_rooms.Rooms._get_available_rooms(
                self=self,
                payload={
                    "pms_property_id": self.pms_property_id.id,
                    "pricelist_id": self.pricelist_id.id,
                    "checkin": self.checkin,
                    "checkout": self.checkout,
                    "reservation_id": self.id,
                },
            ),
            "checkin": self.checkin.strftime(get_lang(self.env).date_format),
            "checkout": self.checkout.strftime(get_lang(self.env).date_format),
            "adults": self.adults,
        }

    def _get_reservation_read_only_fields(self):
        self.ensure_one()
        fields_readonly = [("nights")]
        if self.channel_type_id.is_on_line:
            fields_readonly.extend(
                [
                    "channel_type_id",
                    "pms_property_id",
                    "room_type_id",
                    "agency_id",
                    "user_name",
                    "checkin",
                    "checkout",
                    "adults",
                    "reservation_type",
                    "pricelsit_id",
                    "board_service_room_id",
                    "reservation_line_ids",
                ]
            )
        return fields_readonly

    def _get_checkin_read_only_fields(self, checkin):
        fields_readonly = []
        return fields_readonly

    def _get_checkin_invisible_fields(self, checkin):
        fields_invisible = []
        return fields_invisible
