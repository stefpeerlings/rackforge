function normalizeRoutePath(pathname) {
  let path = String(pathname || "/").replace(/\.html$/, "");
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return path || "/";
}

const Routes = {
  LOGIN: "/login",
  APP: "/main",

  currentPath() {
    return normalizeRoutePath(location.pathname);
  },

  isLoginPage() {
    return this.currentPath() === this.LOGIN;
  },

  isAppPage() {
    return this.currentPath() === this.APP;
  },

  loginUrl(extraParams) {
    const url = new URL(this.LOGIN, location.origin);
    if (extraParams) {
      for (const [key, value] of Object.entries(extraParams)) {
        if (value != null && value !== "") url.searchParams.set(key, value);
      }
    }
    return `${url.pathname}${url.search}${url.hash}`;
  },

  appUrl(extraParams) {
    const url = new URL(this.APP, location.origin);
    if (extraParams) {
      for (const [key, value] of Object.entries(extraParams)) {
        if (value != null && value !== "") url.searchParams.set(key, value);
      }
    }
    return `${url.pathname}${url.search}${url.hash}`;
  },
};

window.Routes = Routes;