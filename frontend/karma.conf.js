module.exports = function (config) {
  config.set({
    frameworks: ["jasmine", "webpack"],
    files: ["src/**/*.spec.js"],
    preprocessors: {
      "src/**/*.spec.js": ["webpack"],
    },
    webpack: {
      module: {
        rules: [
          {
            test: /\.scss$/,
            use: ["style-loader", "css-loader", "sass-loader"],
          },
        ],
      },
    },
    reporters: ["progress"],
    browsers: ["Chrome"],
    singleRun: false,
    concurrency: Infinity,
  });
};
