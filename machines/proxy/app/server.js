var express  = require('express');
var net = require('net');
var app      = express();
var httpProxy = require('http-proxy');
var proxy = httpProxy.createProxyServer();
const web_o = Object.values(require('http-proxy/lib/http-proxy/passes/web-outgoing'));

const options = {
    odoo_tcp_check: true
};

const server_odoo = {
    protocol: 'http',
    port: Number(process.env.INTERNAL_ODOO_PORT),
    host: process.env.INTERNAL_ODOO_HOST,
};
console.log(server_odoo);

const server_calendar = {
    protocol: 'http',
    host: 'calendar',
    port: 80
};

if (process.env.ODOO_VERSION == "9.0") {
    options.odoo_tcp_check = false;
    server_odoo.port = 8072;
}


function _make_davical_path(path) {
    let a = path.split("/"); //a = ["", "caldav", "user1", ]
    if (path.indexOf('/caldav/') === 0) {
        a[1] = 'caldav.php'; 
        a = a.join('/');
        return a;
    }

}

function _call_proxy(req, res, url) {
    proxy.web(req, res, {target: url,
        selfHandleResponse: true
    }, (e) => {
        res.status(500).end();
    });
}

function _wait_tcp_conn(target) {
    return new Promise((resolve, reject) => {
        let do_connect = () => {
            var client = net.connect({host: target.host, port: target.port}, () => {
                resolve();
                client.end()
            });
            client.on('error', function(e) {
                console.log("Error connecting to odoo");
                client.end();
                setTimeout(() => {
                    do_connect();
                }, 100);
            });
        };
        do_connect();
    });
}

proxy.on('proxyReq', (proxyReq, req, res, options) =>  {
    if (req.url.indexOf('/caldav/') == 0) {
        var rewritten_path = _make_davical_path(proxyReq.path);
        proxyReq.path = rewritten_path;
    }
});

proxy.on('proxyRes', (proxyRes, req, res) => {
    //hack: https://github.com/nodejitsu/node-http-proxy/issues/1263
    //ohne dem geht caldav nicht
    for(var i=0; i < web_o.length; i++) {
      if(web_o[i](req, res, proxyRes, {})) { break; }
    }

    proxyRes.pipe(res);
});

app.all("/caldav/*", (req, res, next) => {
    _call_proxy(req, res, server_calendar);
});
 
app.all("/*", (req, res, next) => {
    if (options.odoo_tcp_check) {
        _wait_tcp_conn(server_odoo).then(() => {
            _call_proxy(req, res, server_odoo);
        });
    }
    else {
        _call_proxy(req, res, server_odoo);
    }
});

app.listen(80, '0.0.0.0', () => {
    console.log('Proxy server listening on 80 all interfaces.');
});
