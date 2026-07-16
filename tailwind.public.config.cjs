const path = require('node:path');

const runtimeTailwind = {};
global.tailwind = runtimeTailwind;
require('./dist/js/tailwind.config.js');
delete global.tailwind;

module.exports = {
    ...runtimeTailwind.config,
    content: [
        path.join(__dirname, 'dist/**/*.html'),
        path.join(__dirname, 'dist/js/*.js'),
        path.join(__dirname, 'backend/app/web/company_pages.py'),
        path.join(__dirname, 'backend/app/web/tutorial_pages.py'),
    ],
};
