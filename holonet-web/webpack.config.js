const path = require('path');
const webpack = require('webpack');
const ExtractTextPlugin = require('extract-text-webpack-plugin');
const ManifestRevisionPlugin = require('manifest-revision-webpack-plugin');

const rootAssetPath = './assets';

module.exports = {
    entry: {
        base_css: [
            path.resolve(rootAssetPath, 'styles/base.scss'),
        ],
        base_js: [
            path.resolve(rootAssetPath, 'scripts/base.js'),
        ],
    },
    output: {
        path: path.resolve(__dirname, 'build/public'),
        publicPath: '/assets/',
        filename: '[name].[chunkhash].js',
        chunkFilename: '[id].[chunkhash].js',
    },
    resolve: {
        extensions: ['.js', '.css', '.scss'],
    },
    module: {
        loaders: [
            {
                test: /\.js$/i,
                exclude: /node_modules/,
                loader: 'babel-loader',
            },
            {
                test: /\.css$/i,
                loader: ExtractTextPlugin.extract({
                    fallback: 'style-loader',
                    use: 'css-loader',
                }),
            },
            {
                test: /\.scss$/i,
                loader: ExtractTextPlugin.extract({
                    fallback: 'style-loader',
                    use: ['css-loader', 'sass-loader'],
                }),
            },
            {
                test: /\.(jpe?g|png|gif|svg|eot|ttf|woff|woff2)$/i,
                loader: 'url-loader?limit=8192',
            },
        ]
    },
    plugins: [
        new ExtractTextPlugin('[name].[chunkhash].css'),
        new ManifestRevisionPlugin(path.join('build', 'manifest.json'), {
            rootAssetPath: rootAssetPath,
            ignorePaths: ['/styles', '/scripts'],
        }),
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            'window.jQuery': 'jquery',
            Popper: ['popper.js', 'default'],
        }),
        new webpack.optimize.UglifyJsPlugin(),
    ],
}
