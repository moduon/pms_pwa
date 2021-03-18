# Copyright 2020 Comunitea SL / Alejandro Núñez Liz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class PmsService(models.Model):
    _inherit = "pms.service"

    def _get_service_line_ids(self):
        """
        @return: Return dict with service_line_ids
         [
          {"id": id, "day_qty": day_qty, "date": date},
          {"id": id, "day_qty": day_qty, "date": date},
          ...
          {"id": id, "day_qty": day_qty, "date": date},
         ]
        """
        self.ensure_one()
        service_line_ids = []
        for line in self.service_line_ids:
            service_line_ids.append(
                {
                    "id": line.id,
                    "day_qty": line.day_qty,
                    "date": line.date,
                }
            )
        return service_line_ids
