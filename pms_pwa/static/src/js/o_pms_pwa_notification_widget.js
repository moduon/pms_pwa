odoo.define("pms_pwa.NotifyWidget", function (require) {
    "use strict";

    require("web.dom_ready");
    var ajax = require("web.ajax");
    var core = require("web.core");
    var qweb = core.qweb;
    const session = require("web.session");

    var ReservationTableWidget = require("pms_pwa.reservation_table");

    ajax.loadXML(
        "/pms_pwa/static/src/xml/pms_pwa_roomdoo_notification_widget.xml",
        qweb
    );

    ajax.loadXML("/pms_pwa/static/src/xml/pms_pwa_roomdoo_user_notification.xml", qweb);

    var publicWidget = require("web.public.widget");

    publicWidget.registry.NotifyWidget = publicWidget.Widget.extend({
        selector: ".o_pms_pwa_notify_widget, .o_pms_pwa_cloud_dropdown_menu",
        events: {
            "click a.o_pms_pwa_open_reservation_modal": "_onClickReservationButton",
            "click i.o_pms_pwa_remove_alert": "_onClickDismissAlert",
        },

        init: function () {
            this._super.apply(this, arguments);
        },

        start: function () {
            return this._super.apply(this, arguments);
        },

        alertButtonsOnClick: function () {
            var self = this;
            $(".o_pms_pwa_notify_widget a.o_pms_pwa_open_reservation_modal").on(
                "click",
                function (event) {
                    event.preventDefault();
                    self._onClickReservationButton(event);
                }
            );
        },

        cloudColorToDefault: function () {
            $(".o_pms_pwa_cloud_dropdown")
                .find("img")
                .attr("src", "/pms_pwa/static/img/svg/cloud.svg")
                .removeClass("o_pms_pwa_cloud_on")
                .addClass("o_pms_pwa_cloud_off");
        },

        _onClickReservationButton: function (event) {
            event.stopImmediatePropagation();
            event.preventDefault();
            new ReservationTableWidget(this)._openModalFromExternal(event);
            this.cloudColorToDefault();
        },

        _onClickDismissAlert: function (event) {
            event.stopPropagation();
            event.preventDefault();
            event.currentTarget.parentNode.remove();
        },

        recalculateNotificationsSpan: function (span) {
            if (parseInt(span.text()) > 0 && span.hasClass("d-none")) {
                span.removeClass("d-none");
            } else if (parseInt(span.text()) <= 0 && !span.hasClass("d-none")) {
                span.addClass("d-none");
            }
        },

        reloadUserPropertyNotifications: function (pms_property) {
            var self = this;
            this._rpc({
                model: "res.users",
                method: "get_user_notification_list",
                args: [[session.user_id]],
            }).then(function (user_notification_ids) {
                console.log("user_notification_ids", user_notification_ids);
                var notifications_button = $(
                    ".notifications_property_" + String(pms_property)
                );
                if (notifications_button.length > 0 && user_notification_ids) {
                    var notifications_container = qweb.render(
                        "pms_pwa.user_notification_widget",
                        {
                            user_notification_ids: user_notification_ids,
                        }
                    );
                    notifications_button.html(notifications_container);
                }
            });
        },

        displayDataAlert: function (data) {
            var self = this;
            var message = JSON.parse(data.message);
            var alert_div = $(".o_pms_pwa_notify_widget");
            var alert = qweb.render("pms_pwa.notification_widget", {
                alert: message,
            });
            alert_div.append(alert);

            // Browser does not allow playing audio without user interaction. TO REVIEW

            if (message.audio) {
                var audio = new Audio(message.audio);
                audio.play();
            }

            if (message.pms_property) {
                var tab = $("a#property-tab-" + message.pms_property);
                if (tab.length > 0) {
                    var unread_qty = tab.find("span.o_pms_pwa_rounded_alert");
                    if (unread_qty.length > 0) {
                        unread_qty.text(parseInt(unread_qty.text()) + 1);
                        self.recalculateNotificationsSpan(unread_qty);
                    }
                }

                this.reloadUserPropertyNotifications(message.pms_property);
            }

            self.alertButtonsOnClick();

            self.addNotificationToCloud(data);
            self.calculateCloudColor();
        },

        addNotificationToCloud: function (notification) {
            var cloud_div = $(".o_pms_pwa_cloud_dropdown_menu");
            var message = JSON.parse(notification.message);
            if (message.id) {
                var notification = $("<a></a>")
                    .addClass("dropdown-item o_pms_pwa_open_reservation_modal")
                    .html(
                        message.message +
                            "<i class='fa fa-trash o_pms_pwa_remove_alert ml-2'></i>"
                    )
                    .attr("href", "#")
                    .attr("data-id", message.id);
            } else {
                var notification = $("<a></a>")
                    .addClass("dropdown-item")
                    .html(
                        message.message +
                            "<i class='fa fa-trash o_pms_pwa_remove_alert ml-2'></i>"
                    )
                    .attr("href", "#");
            }

            cloud_div.append(notification);
        },

        calculateCloudColor: function () {
            var child_count = 0;
            var cloud_off = false;
            try {
                child_count = $(".o_pms_pwa_cloud_dropdown_menu").get(0)
                    .childElementCount;
                var cloud = $(".o_pms_pwa_cloud_dropdown").find(
                    "img.o_pms_pwa_cloud_off"
                );
                if (cloud.length > 0) {
                    cloud_off = true;
                }
            } catch (error) {
                console.log(error);
            }

            if (child_count > 0 && cloud_off) {
                $(".o_pms_pwa_cloud_dropdown")
                    .find("img")
                    .attr("src", "/pms_pwa/static/img/svg/cloud-to-assign.svg")
                    .removeClass("o_pms_pwa_cloud_off")
                    .addClass("o_pms_pwa_cloud_on");
            }
        },
    });

    return publicWidget.registry.NotifyWidget;
});
