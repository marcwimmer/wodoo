odoo.define("View.Followup.Dashboard", function(require) {
	var core = require('web.core');
	var formats = require('web.formats');
	var Model = require('web.Model');
	var session = require('web.session');
	var KanbanView = require('web_kanban.KanbanView');

	var QWeb = core.qweb;

	var _t = core._t;
	var _lt = core._lt;

	var FollowupDashboardView = KanbanView.extend({
		display_name: _lt('Follow-Ups'),
		icon: 'fa-dashboard',
		view_type: "followup_dashboard",
		searchview_hidden: true,
		render: function() {
			var self = this;
			this._super.apply(this, arguments);
			
		},
	});

	core.view_registry.add('followup_dashboard', FollowupDashboardView);
	return FollowupDashboardView;
});
