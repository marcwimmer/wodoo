var express  = require('express');
var net = require('net');
var httpProxy = require('http-proxy');
var proxy = httpProxy.createProxyServer();
const web_o = Object.values(require('http-proxy/lib/http-proxy/passes/web-outgoing'));
var serveStatic = require('serve-static');
var serveIndex = require('serve-index');



const { createProxyMiddleware } = require('http-proxy-middleware');
var app      = express();

const options = {
    odoo_tcp_check: true
};

const server_odoo = {
    protocol: 'http',
    host: process.env.ODOO_HOST,
    port: 8069,
};


function _call_proxy(req, res, url) {
    proxy.web(req, res, {
        target: url,
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
                console.log("Error connecting to " + target + ": " + (new Date()));
                client.end();
                setTimeout(() => {
                    do_connect();
                }, 100);
            });
        };
        do_connect();
    });
}

proxy.on('proxyRes', (proxyRes, req, res) => {
    //hack: https://github.com/nodejitsu/node-http-proxy/issues/1263
    //ohne dem geht caldav nicht
    for(var i=0; i < web_o.length; i++) {
      if(web_o[i](req, res, proxyRes, {})) { break; }
    }

    proxyRes.pipe(res);
});

app.use(
    "/robot-output",
    express.static(__dirname + "/odoo/robot_output"),
    serveIndex(__dirname + "/odoo/robot_output", {'icons': true})
);
app.use("/mailer",createProxyMiddleware({
    target: 'http://' + process.env.ROUNDCUBE_HOST + ':80',
})); 

app.use("/code",createProxyMiddleware({
    target: 'http://theia' + process.env.THEIA_HOST + ':3000',
})); 

app.use("/longpolling", createProxyMiddleware({
    target: 'http://' + process.env.ODOO_HOST + ':8072',
})); 

// app.use("/console", createProxyMiddleware({
//     target: 'http://' + process.env.WEBSSH_HOST + ':80',
//     ws: true,
// })); 


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
    console.log('Proxy server listening on 0.0.0.0:80.');
});
server.setTimeout(3600 * 100000);
