$(document).ready(function() {

    $(".docker-control").click(function() {
        debugger;
        var $el = $(this);
        var action = $el.data('action')
        var name = $el.data('name');
        $.get("/instance/" + action + "?name=" + name).then(function(result) {
            debugger;
        });
    });
    alert("HI");
});
