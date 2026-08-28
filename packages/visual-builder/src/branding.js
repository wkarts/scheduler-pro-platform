const BRAND_LOGO_LIGHT_URL = new URL('../assets/brand/argws-visual-builder-logo-1600.png', import.meta.url).href;
const BRAND_LOGO_DARK_URL = new URL('../assets/brand/argws-visual-builder-logo-dark.png', import.meta.url).href;
const BRAND_SYMBOL_URL = new URL('../assets/brand/argws-visual-builder-symbol-64.png', import.meta.url).href;

export const AVB_BRAND_ASSETS = Object.freeze({
  lightLogo: BRAND_LOGO_LIGHT_URL,
  darkLogo: BRAND_LOGO_DARK_URL,
  symbol: BRAND_SYMBOL_URL,
});

export function resolveAvbBrandLogo(theme = 'light') {
  return String(theme).toLowerCase() === 'dark' ? AVB_BRAND_ASSETS.darkLogo : AVB_BRAND_ASSETS.lightLogo;
}
