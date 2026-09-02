/**
 * Configuración de ESLint del panel B2B.
 *
 * Se usa el formato `eslintrc` y no el `flat config` porque el script `lint`
 * del `package.json` invoca `--ext ts,tsx`, una opción que solo existe en este
 * formato, y porque ESLint 8 —la versión fijada— todavía lo trata como el
 * predeterminado.
 *
 * Las reglas que van más allá de lo recomendado están puestas por el tipo de
 * datos que este panel muestra: cédulas, biometría y evidencia pericial.
 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  ignorePatterns: ["dist", "node_modules", ".eslintrc.cjs", "*.config.js"],
  rules: {
    ...require("eslint-plugin-react-hooks").configs.recommended.rules,

    // El panel proyecta evidencia con valor pericial: un `any` acá es una
    // estructura de evidencia sin verificar.
    "@typescript-eslint/no-explicit-any": "error",

    // Una variable sin usar en un componente que muestra datos sensibles suele
    // ser un campo que se dejó de renderizar sin quitarlo del origen.
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],

    // `console.log` es la vía más común por la que un dato personal termina en
    // un registro del navegador o en la consola de un tercero (regla inviolable
    // de aislamiento de datos sensibles). Se permiten los canales de error.
    "no-console": ["error", { allow: ["warn", "error"] }],

    eqeqeq: ["error", "always"],
  },
};
