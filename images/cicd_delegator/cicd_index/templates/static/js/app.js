$(document).ready(function() {

    $(".docker-control").click(function() {
        var $el = $(this);
        var action = $el.data('action')
        var name = $el.data('name');
    });
    alert("HI");
});
