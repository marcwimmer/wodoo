import os
from pathlib import Path


autologin = """
<script>
    setTimeout(function() {
    $("#rcmloginuser").val("postmaster");
    $("#rcmloginpwd")[0].value = "postmaster";
    $("form")[0].submit();
    });
</script>
"""
file = Path("/usr/share/nginx/www/skins/elastic/templates/login.html")
text = file.read_text()
text += autologin
file.write_text(text)
