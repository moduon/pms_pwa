odoo.define("pms_pwa.reduced_calendar", function (require) {
    "use strict";
    require("web.dom_ready");
    var ajax = require("web.ajax");
    var core = require("web.core");
    var publicWidget = require("web.public.widget");
    var csrf_token = core.csrf_token;
    const date_options = {year: "numeric", month: "2-digit", day: "2-digit"};
    var calendar_dpr = $('input[name="calendar_dpr"]').val();

    publicWidget.registry.ReducedCalendarCollapseWidget = publicWidget.Widget.extend({
        selector: "#reduced_calendar_table, #confirmChange",
        xmlDependencies: ["/pms_pwa/static/src/xml/pms_pwa_roomdoo_reduced_calendar_line.xml"],
        events: {
            "click tr.o_pms_pwa_open_reduced_calendar": "_onClickGetCalendarLine",
            "click .close_confirmChange": "_onClickCloseModal",
        },
        launchLines: function (event) {
            var data_id = event.getAttribute("data-id");
            var date_list = $('input[name="date_list"]').val();
            var selected_display = $('input[name="selected_display"]').val();
            ajax.jsonRpc("/calendar/line", "call", {
                data_id: data_id,
                range_date: date_list,
                selected_display: selected_display,
            }).then(function (data) {
                var html = core.qweb.render("pms_pwa.reduced_calendar_line", {
                    data_id: data_id,
                    obj_list: data.reservations,
                    csrf_token: csrf_token,
                });
                $(String("#collapse_accordion_" + data_id)).html(html);
                $(String("#collapse_accordion_"+data_id)).addClass("show");

                // RESIZE:
                // $(".o_pms_pwa_line_cell_content")
                // .css({
                //     /* required to allow resizer embedding */
                //     position: "relative",
                //     // index: '9999'
                // })
                // /* check .resizer CSS */
                // .prepend("<div class='resizer'></div>")
                // .resizable({
                //     resizeHeight: false,
                //     resizeHeightFrom: false,
                //     // we use the column as handle and filter
                //     // by the contained .resizer element
                //     handleSelector: ".o_pms_pwa_resize",
                //     onDragStart: function(e, $el, opt) {
                //     // only drag resizer
                //     if (!$(e.target).hasClass("resizer"))
                //         return false;
                //     return true;
                //     }
                // });
                // $(".o_pms_pwa_calendar_reservation" ).resizable({
                //     handleSelector: ".o_pms_pwa_calendar_line",
                //     resizeHeight: false,
                // });

                // ESTO PARA CREAR EL DRAG
                $(".o_pms_pwa_reduced_calendar_reservation").draggable({
                    containment: "#reduced_calendar_table",
                    revert: "invalid",
                    start: function( event, ui ) {
                        console.log("event--->", event.currentTarget);
                        console.log("ui--->", ui);
                        $(event.currentTarget).addClass('z-index-all');
                        $(".o_pms_pwa_line_cell_content").removeAttr('style');
                        $(".o_pms_pwa_line_cell_content").draggable();
                   }
                });
                // ESTO PARA VER DONDE IR Y DROP PARA CONOCER DONDE SE SUELTA
                $(".o_pms_pwa_line_cell_content").droppable({
                    // CLASES PARA MOSTRAR CUADROS ACTIVOS Y COLOR DE HOVER
                    classes: {
                        "ui-droppable-active": "ui-state-active",
                        "ui-droppable-hover": "ui-state-hover"
                    },
                    drop: function(event, ui) {
                        console.log("drop event--->", event);
                        console.log("drop ui--->", ui);
                        ajax.jsonRpc("/calendar/reduced-change", "call", {
                            id:  ui.draggable.data('id'),
                            date:  event.target.dataset.date,
                            room:  event.target.dataset.calendarRoom,
                            // selected_display: selected_display,
                        }).then(function (data) {
                            console.log("devuelve --->", data);

                            if (data && String(data['result']) == "success") {
                                // LANZO MODAL DE CONFIRMACIÓN
                                $('#confirmChange').on('show.bs.modal', function (event) {
                                    var button = $(event.relatedTarget)
                                    var recipient = button.data('whatever')
                                    var modal = $(this)
                                    modal.find('.modal-title').text("Confirmar cambio")
                                    modal.find('.modal-body p').text(String(data['message']))
                                });
                                $('#confirmChange').modal('show');
                            } else{
                                //LANZO WARNNING
                                data['type'] = "warning";
                                if(!data['message']){
                                    data['message'] = "Se ha producido un error al procesar los datos.";
                                }
                                var alert_div = $(".o_pms_pwa_roomdoo_alerts");
                                var alert = core.qweb.render("pms_pwa.reservation_alerts", {
                                    alert: data,
                                });
                                alert_div.append(alert);
                                jQuery.ready();
                                $(".o_pms_pwa_line_cell_content").removeAttr('style');

                                // Destroy original draggable and create new one
                                $(".o_pms_pwa_line_cell_content").draggable("destroy");
                                $(".o_pms_pwa_line_cell_content").draggable();
                            }
                            // EJEMPLO DE COMO AÑADIR AUDIO
                            // var audio = new Audio('https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3');
                            // audio.play();
                        });
                        $(this).effect("highlight", {}, 1500);
                    },
                    // over: function(event, ui) {
                    //     console.log("over event--->", event);
                    //     console.log("over ui--->", ui);
                    //     $(this).css('background', 'cyan');
                    // },
                    // out: function(event, ui) {
                    //     console.log("out event--->", event);
                    //     console.log("out ui--->", ui);
                    //     $(this).css('background', 'orange');
                    //     $(".o_pms_pwa_line_cell_content").removeAttr('style');
                    //     $(".o_pms_pwa_line_cell_content").draggable();
                    // }
                });
            });
        },
        init: function(){
            console.log("init");
            var self = this;
            // $(".o_pms_pwa_open_reduced_calendar").map(function() {
            //     self.launchLines(this);
            // }).get();
            return this._super.apply(this, arguments);

        },
        _onClickCloseModal: function (event) {
            $(".o_pms_pwa_line_cell_content").removeAttr('style');
            $(".o_pms_pwa_line_cell_content").draggable();
        },
        _onClickGetCalendarLine: function (event) {
            var self = this;
            event.preventDefault();
            self.launchLines(event.currentTarget);
        },
    });
});

