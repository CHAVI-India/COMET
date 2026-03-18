const path = require('path');

module.exports = {
  entry: './src/index.js',
  output: {
    filename: 'cornerstone-segmentation.bundle.js',
    path: path.resolve(__dirname, 'dist'),
    library: {
      name: 'CornerstoneSegmentation',
      type: 'umd',
      export: 'default'
    },
    globalObject: 'this'
  },
  mode: 'production',
  resolve: {
    extensions: ['.js', '.mjs'],
    mainFields: ['module', 'main'],
    conditionNames: ['import', 'module', 'default'],
    alias: {
      'cornerstone3D': '@cornerstonejs/core'
    },
    fallback: {
      "fs": false,
      "path": false,
      "crypto": false,
      "stream": false,
      "buffer": false,
      "url": false,
      "http": false,
      "https": false,
      "zlib": false,
      "assert": false,
      "util": false
    }
  },
  module: {
    rules: [
      {
        test: /\.m?js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      }
    ]
  }
};
