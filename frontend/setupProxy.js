const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  const apiEndpoints = [
    '/login',
    '/training-status',
    '/start-training',
    '/check-in',
    '/predict' // Assuming you will add a predict endpoint
  ];

  apiEndpoints.forEach(endpoint => {
    app.use(
      endpoint,
      createProxyMiddleware({
        target: 'http://10.48.242.137:5000',
        changeOrigin: true,
      })
    );
  });
};