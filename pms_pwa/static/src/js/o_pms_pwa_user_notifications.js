odoo.define("pms_pwa.UserNotifications", function (require) {
    "use strict";

    require("web.dom_ready");
    var ajax = require("web.ajax");
    var core = require("web.core");
    var _t = core._t;
    var publicWidget = require("web.public.widget");
    var ReservationTableWidget = require("pms_pwa.reservation_table");
    var NotifyWidget = require("pms_pwa.NotifyWidget");

    publicWidget.registry.UserNotificationsWidget = publicWidget.Widget.extend({
        selector: ".o_pms_pwa_roomdoo",
        events: {
            "click a.o_pms_pwa_open_reservation_modal":
                "_onClickPMSPWAOpenReservationModal",
            "click i.o_pms_pwa_remove_alert": "_onClickPMSPWARemoveAlert",
        },

        init: function () {
            this._super.apply(this, arguments);
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments);
        },

        _onClickPMSPWARemoveAlert: function (ev) {
            var self = this;

            try {
                var reservation_id = ev.currentTarget.getAttribute("data-id");
                var pms_property_id = ev.currentTarget.getAttribute(
                    "data-pms_property_id"
                );
                this._rpc({
                    model: "res.users.notifications",
                    method: "mark_as_read",
                    args: [[parseInt(reservation_id)]],
                });
                // Metiéndolo en el then hace todo menos el reloadUserPropertyNotifications. REVISAR
                setTimeout(function () {
                    ev.currentTarget.parentNode.remove();
                    var tab = $("a#property-tab-" + String(pms_property_id));
                    if (tab.length > 0) {
                        var unread_qty = tab.find("span.o_pms_pwa_rounded_alert");
                        if (unread_qty.length > 0) {
                            unread_qty.text(parseInt(unread_qty.text()) - 1);
                            new NotifyWidget(this).recalculateNotificationsSpan(
                                unread_qty
                            );
                        }
                    }
                }, 0);
                new NotifyWidget(this).reloadUserPropertyNotifications(pms_property_id);
            } catch (error) {
                console.log(error);
            }
        },

        _onClickPMSPWAOpenReservationModal: function (ev) {
            var self = this;
            new ReservationTableWidget(this)._openModalFromExternal(ev);
        },
    });

    return publicWidget.registry.PropertySelectorWidget;
});