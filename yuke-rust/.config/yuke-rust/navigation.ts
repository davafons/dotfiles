export interface NavigationBridge {
  focusSession: (id: string) => Promise<boolean>;
  openFile: (url: string, cwd: string) => Promise<void>;
}

export interface Navigation {
  installBridge: (bridge: NavigationBridge) => () => void;
  openSession: (id: string) => Promise<void>;
  openFile: (path: string, line?: number, column?: number) => Promise<void>;
}

declare module "yuke:plugins" {
  interface Services {
    readonly "personal-navigation": Navigation;
  }
}
