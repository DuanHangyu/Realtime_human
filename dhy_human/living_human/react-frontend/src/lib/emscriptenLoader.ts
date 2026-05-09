// Emscripten module loader - wraps Load1 from original load.js

interface LoadConfig {
  qt: {
    onLoaded?: () => void;
    entryFunction?: (config: any) => Promise<any>;
    containerElements?: HTMLElement[];
    qtdir?: string;
    preload?: any[];
    environment?: Record<string, string>;
    onExit?: (info: { code?: number; text?: string; crashed: boolean }) => void;
    module?: Promise<WebAssembly.Module>;
    fontDpi?: number;
  };
  [key: string]: any;
}

declare global {
  interface Window {
    createQtAppInstance: (config: any) => Promise<any>;
  }
}

export async function loadEmscriptenModule(
  screenElement: HTMLElement
): Promise<any> {
  const config: LoadConfig = {
    qt: {
      onLoaded: () => {
        screenElement.style.display = 'block';
      },
      entryFunction: window.createQtAppInstance,
      containerElements: [screenElement],
    },
  };

  return Load1(config);
}

async function Load1(config: LoadConfig): Promise<any> {
  const throwIfEnvUsedButNotExported = (instance: any, config: LoadConfig) => {
    const environment = config.qt.environment;
    if (!environment || Object.keys(environment).length === 0) return;
    const isEnvExported = typeof instance.ENV === 'object';
    if (!isEnvExported)
      throw new Error('ENV must be exported if environment variables are passed');
  };

  const throwIfFsUsedButNotExported = (instance: any, config: LoadConfig) => {
    const environment = config.qt.environment;
    if (!environment || Object.keys(environment).length === 0) return;
    const isFsExported = typeof instance.FS === 'object';
    if (!isFsExported)
      throw new Error('FS must be exported if preload is used');
  };

  if (typeof config !== 'object')
    throw new Error('config is required, expected an object');
  if (typeof config.qt !== 'object')
    throw new Error('config.qt is required, expected an object');
  if (typeof config.qt.entryFunction !== 'function')
    config.qt.entryFunction = window.createQtAppInstance;

  config.qt.qtdir ??= 'qt';
  config.qt.preload ??= [];

  (config as any).qtContainerElements = config.qt.containerElements;
  delete config.qt.containerElements;
  (config as any).qtFontDpi = config.qt.fontDpi;
  delete config.qt.fontDpi;

  let circuitBreakerReject: (reason: any) => void;
  const circuitBreaker = new Promise((_, reject) => {
    circuitBreakerReject = reject;
  });

  if (config.qt.module) {
    (config as any).instantiateWasm = async (imports: any, successCallback: any) => {
      try {
        const module = await config.qt.module!;
        successCallback(
          await WebAssembly.instantiate(module, imports),
          module
        );
      } catch (e) {
        circuitBreakerReject(e);
      }
    };
  }

  const qtPreRun = (instance: any) => {
    throwIfEnvUsedButNotExported(instance, config);
    for (const [name, value] of Object.entries(config.qt.environment ?? {}))
      instance.ENV[name] = value;

    const makeDirs = (FS: any, filePath: string) => {
      const parts = filePath.split('/');
      let path = '/';
      for (let i = 0; i < parts.length - 1; ++i) {
        const part = parts[i];
        if (part == '') continue;
        path += part + '/';
        try {
          FS.mkdir(path);
        } catch (error: any) {
          const EEXIST = 20;
          if (error.errno != EEXIST) throw error;
        }
      }
    };
    throwIfFsUsedButNotExported(instance, config);
    for (const { destination, data } of (self as any).preloadData) {
      makeDirs(instance.FS, destination);
      instance.FS.writeFile(destination, new Uint8Array(data));
    }
  };

  if (!(config as any).preRun) (config as any).preRun = [];
  (config as any).preRun.push(qtPreRun);

  (config as any).onRuntimeInitialized = () => config.qt.onLoaded?.();

  const originalLocateFile = (config as any).locateFile;
  (config as any).locateFile = (filename: string) => {
    const originalLocatedFilename = originalLocateFile
      ? originalLocateFile(filename)
      : filename;
    if (originalLocatedFilename.startsWith('libQt6'))
      return `${config.qt.qtdir}/lib/${originalLocatedFilename}`;
    return originalLocatedFilename;
  };

  const originalOnExit = (config as any).onExit;
  (config as any).onExit = (code: number) => {
    originalOnExit?.();
    config.qt.onExit?.({ code, crashed: false });
  };

  const originalOnAbort = (config as any).onAbort;
  (config as any).onAbort = (text: string) => {
    originalOnAbort?.();
    config.qt.onExit?.({ text, crashed: true });
  };

  const fetchPreloadFiles = async () => {
    const fetchJson = async (path: string) => (await fetch(path)).json();
    const fetchArrayBuffer = async (path: string) =>
      (await fetch(path)).arrayBuffer();
    const loadFiles = async (paths: any) => {
      const source = paths['source'].replace('$QTDIR', config.qt.qtdir!);
      return {
        destination: paths['destination'],
        data: await fetchArrayBuffer(source),
      };
    };
    const fileList = (
      await Promise.all(config.qt.preload!.map(fetchJson))
    ).flat();
    (self as any).preloadData = (
      await Promise.all(fileList.map(loadFiles))
    ).flat();
  };

  await fetchPreloadFiles();

  let instance: any;
  try {
    instance = await Promise.race([
      circuitBreaker,
      config.qt.entryFunction!(config),
    ]);
  } catch (e: any) {
    config.qt.onExit?.({ text: e.message, crashed: true });
    throw e;
  }

  return instance;
}
