/** Configuración de ESLint del SDK. Mismo criterio que el resto del repositorio. */
module.exports = {
  root: true,
  env: { es2022: true, node: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["@typescript-eslint"],
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended"],
  ignorePatterns: ["node_modules", "dist", ".eslintrc.cjs"],
  rules: {
    // Un `any` en el SDK del contrato se propaga a todos los integradores.
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    // El SDK maneja datos del firmante: nada va a la consola.
    "no-console": "error",
    eqeqeq: ["error", "always"],
  },
};
