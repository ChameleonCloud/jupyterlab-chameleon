import {
  ILayoutRestorer, JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import {
  ICommandPalette,
  MainAreaWidget,
  WidgetTracker
} from '@jupyterlab/apputils';
import { FileBrowser, IFileBrowserFactory } from '@jupyterlab/filebrowser';
import { IMainMenu } from '@jupyterlab/mainmenu';
import { Contents } from '@jupyterlab/services';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { Menu } from '@lumino/widgets';
import { IArtifactSharingURL } from './tokens';
import { ArtifactSharingWidget } from './widget';

const PLUGIN_ID = '@chameleoncloud/jupyterlab-chameleon:artifact-sharing';

export class ArtifactSharingURL implements IArtifactSharingURL {
  constructor(settings: ISettingRegistry.ISettings) {
    this._settings = settings;
  }

  indexUrl(): string {
    return this._baseUrl;
  }
  detailUrl(externalId: string): string {
    return this._makeUrl('externalDetailEndpoint')
      .replace('{externalId}', externalId);
  }
  createUrl(artifactId: string): string {
    return this._makeUrl('externalCreateEndpoint')
      .replace('{artifactId}', artifactId);
  }
  updateUrl(externalId: string): string {
    return this._makeUrl('externalUpdateEndpoint')
      .replace('{externalId}', externalId);
  }
  newVersionUrl(externalId: string, artifactId: string): string {
    return this._makeUrl('externalNewVersionEndpoint')
      .replace('{externalId}', externalId)
      .replace('{artifactId}', artifactId);
  }

  isExternalUrl(origin: string): boolean {
    return this._baseUrl.indexOf(origin) === 0;
  }

  private get _baseUrl(): string {
    return this._settings.get('externalBaseUrl').composite as string;
  }
  private _makeUrl(endpoint: string): string {
    const path = this._settings.get(endpoint).composite as string;
    return this._baseUrl + path;
  }
  private _settings: ISettingRegistry.ISettings;
}

function createOpener(
  app: JupyterFrontEnd,
  settings: ISettingRegistry.ISettings,
  browser: FileBrowser,
  tracker: WidgetTracker<MainAreaWidget<ArtifactSharingWidget>>
) {
  let widget: MainAreaWidget<ArtifactSharingWidget>;

  return async () => {
    const item = browser.selectedItems().next();
    const artifactPath = (item && item.type === 'directory')
      ? item.path : null;

    if (!widget || widget.isDisposed) {
      const urlFactory = new ArtifactSharingURL(settings);
      const content = new ArtifactSharingWidget(artifactPath, urlFactory);
      content.title.label = 'Package artifact';
      widget = new MainAreaWidget({ content });
      widget.id = 'artifact-sharing';
    }

    if (!widget.isAttached) {
      app.shell.add(widget, 'main');
    }

    if (!tracker.has(widget)) {
      await tracker.add(widget);
    }

    widget.update();
    app.shell.activateById(widget.id);
  };
}

const plugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  requires: [
    ISettingRegistry,
    ICommandPalette,
    ILayoutRestorer,
    IMainMenu,
    IFileBrowserFactory
  ],
  activate(
    app: JupyterFrontEnd,
    settingRegistry: ISettingRegistry,
    palette: ICommandPalette,
    restorer: ILayoutRestorer,
    mainMenu: IMainMenu,
    fileBrowserFactory: IFileBrowserFactory
  ): void {
    Promise.all([settingRegistry.load(PLUGIN_ID), app.restored])
      .then(async ([settings]) => {
        const browser = fileBrowserFactory.defaultBrowser;
        const tracker = new WidgetTracker<MainAreaWidget<ArtifactSharingWidget>>({
          namespace: 'artifact-sharing'
        });

        const openWidget = createOpener(app, settings, browser, tracker);

        app.commands.addCommand(CommandIDs.create, {
          label: 'Package as new artifact',
          isEnabled() {
            return Private.currentItemNotShared(browser);
          },
          async execute() {
            await openWidget();
          }
        });

        app.commands.addCommand(CommandIDs.edit, {
          label: 'Edit artifact',
          isEnabled() {
            return Private.currentItemIsShared(browser);
          },
          async execute() {
            await openWidget();
          }
        });

        app.commands.addCommand(CommandIDs.newVersion, {
          label: 'Create new artifact version',
          isEnabled() {
            return Private.currentItemIsShared(browser);
          },
          async execute() {
            await openWidget();
          }
        });

        registerTopMenu(app, mainMenu);
        registerContextMenu(app);
        registerCommandPalette(palette);

        await restorer.restore(tracker, {
          command: CommandIDs.create,
          name: () => 'artifact-sharing'
        });
      })
      .catch((reason: Error) => {
        console.error(reason.message);
      });
  },
  autoStart: true
};

function registerTopMenu(app: JupyterFrontEnd, mainMenu: IMainMenu) {
  const menu = new Menu({ commands: app.commands });
  menu.addItem({ command: CommandIDs.create });
  menu.addItem({ command: CommandIDs.edit });
  menu.addItem({ command: CommandIDs.newVersion });
  menu.title.label = 'Share';
  mainMenu.addMenu(menu, { rank: 20 });
}

function registerCommandPalette(palette: ICommandPalette) {
  const category = 'Sharing';
  palette.addItem({ command: CommandIDs.create, category });
  palette.addItem({ command: CommandIDs.edit, category });
  palette.addItem({ command: CommandIDs.newVersion, category });
}

function registerContextMenu(app: JupyterFrontEnd) {
  const selectorPublished =
    '.jp-DirListing-item[data-isdir=true][data-isshared=true]';
  const selectorNotPublished =
    '.jp-DirListing-item[data-isdir=true]:not([data-isshared=true])';

  app.contextMenu.addItem({
    command: CommandIDs.create,
    selector: selectorNotPublished,
    rank: 1
  });
  app.contextMenu.addItem({
    command: CommandIDs.edit,
    selector: selectorPublished,
    rank: 1
  });
  app.contextMenu.addItem({
    command: CommandIDs.newVersion,
    selector: selectorPublished,
    rank: 2
  });
}

namespace CommandIDs {
  export const create = 'artifact-sharing:create';
  export const edit = 'artifact-sharing:edit';
  export const newVersion = 'artifact-sharing:newVersion';
}

namespace Private {
  export function supportedItem(item?: Contents.IModel) {
    return item && item.type === 'directory';
  }

  export function hasDeposition(item?: Contents.IModel) {
    // No item = check the root path (empty)
    // const path = (item && item.path) || '';
    // TODO
    return false;
  }

  export function currentItemIsShared(browser: FileBrowser) {
    const item = browser.selectedItems().next();
    return supportedItem(item) && hasDeposition(item);
  }

  export function currentItemNotShared(browser: FileBrowser) {
    const item = browser.selectedItems().next();
    return supportedItem(item) && !hasDeposition(item);
  }

  export function currentItemArtifact(browser: FileBrowser) {
    // const item = browser.selectedItems().next();
    // const path = (item && item.path) || '';
    // return zenodoRegistry.getDeposition(path).then(record => {
    //   if (!record) {
    //     throw Error(`No deposition exists at path "${path}"`);
    //   }
    //   return record;
    // });
    // TODO
    return false;
  }
}

export default plugin;
