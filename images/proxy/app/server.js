var express  = require('express');
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
const server_calendar = {
    protocol: 'http',
    host: 'calendar',
    port: 80
};

const server_mail = {
    protocol: 'http',
    host: 'roundcube',
    port: 80
};

const server_longpolling = {
    protocol: 'http',
    host: process.env.ODOO_HOST,
    port: 8072
};

app.use("/mailer",createProxyMiddleware({
    target: 'http://roundcube',
    changeOrigin: true,
    //pathRewrite: {
    //    '^/mailer': '/', 
    //  },
})); 
app.use("/", createProxyMiddleware({
    target: 'http://odoo:8069',
    changeOrigin: true
})); 
 
var server = app.listen(80, '0.0.0.0', () => {
    console.log('Proxy server listening on 0.0.0.0:80.');
});
server.setTimeout(3600 * 100000);
