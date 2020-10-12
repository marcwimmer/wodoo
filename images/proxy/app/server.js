var express  = require('express');
var net = require('net');
var bodyParser = require('body-parser');
var app      = express();
var httpProxy = require('http-proxy');
var cookieParser = require("cookie-parser");
var proxy = httpProxy.createProxyServer();
const web_o = Object.values(require('http-proxy/lib/http-proxy/passes/web-outgoing'));
app.use(bodyParser.raw({limit: '1024mb'}));

app.use(cookieParser());

app.use(function(req, res, next) {

    // set a cookie so that a central redirector can redirect the 
    // odoo session 
    // SETTINGS: SET_CICD_COOKIE
    if (process.env.set_cicd_cookie) {
        var cookie = req.cookies['CICD_ID'];
        if (cookie === undefined) {
            res.cookie('CICD_ID', process.env.dbname, { maxAge: 900000, httpOnly: true });
            console.log('CICD_ID cookie created for ' + process.env.dbname);
        }
    }

    next();
})

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

const server_longpolling = {
    protocol: 'http',
    host: 'odoo',
    port: 8072
};


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
        console.log(e);
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
                console.log("Error connecting to odoo: " + (new Date()));
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

app.all("/longpolling/*", (req, res, next) => {
    _call_proxy(req, res, server_longpolling);
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

var server = app.listen(80, '0.0.0.0', () => {
    console.log('Proxy server listening on 80 all interfaces.');
});
server.setTimeout(3600 * 1000);
