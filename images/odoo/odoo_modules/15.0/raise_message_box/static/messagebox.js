odoo.define('raise.message_box', function(require) { 

    require('web.CrashManager').CrashManager.include({
        rpc_error: function(error) {
            if (error.data && error.data.name && error.data.name.indexOf("raise_message_box") > 0) {
                error.type = ' '; //display empty title
            }
            return this._super.apply(this, arguments);
        }
    });

})
