import { ILayoutRestorer, IRouter, JupyterFrontEnd, JupyterFrontEndPlugin } from '@jupyterlab/application';
import { ICommandPalette, MainAreaWidget, WidgetTracker } from '@jupyterlab/apputils';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { DirListing, FileBrowser, IFileBrowserFactory } from '@jupyterlab/filebrowser';
import fileBrowserPlugins from '@jupyterlab/filebrowser-extension';
import { IMainMenu } from '@jupyterlab/mainmenu';
import { Contents } from '@jupyterlab/services';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { IStateDB } from '@jupyterlab/statedb';
import { ITranslator } from '@jupyterlab/translation';
import { toArray } from '@lumino/algorithm';
import { Menu } from '@lumino/widgets';
import { DirListingRenderer } from './filebrowser';
import { ArtifactRegistry } from './registry';
import { IArtifactRegistry, IArtifactSharingURL, Workflow } from './tokens';
import { ArtifactSharingWidget } from './widget';

const PLUGIN_NAMESPACE = '@chameleoncloud/jupyterlab-chameleon';
const WIDGET_PLUGIN_ID = `${PLUGIN_NAMESPACE}:artifact-sharing`;
const FILE_BROWSER_PLUGIN_ID = `${PLUGIN_NAMESPACE}:file-browser-factory`;
const REGISTRY_PLUGIN_ID = `${PLUGIN_NAMESPACE}:artifact-registry`;

export class ArtifactSharingURL implements IArtifactSharingURL {
  constructor(settings: ISettingRegistry.ISettings) {
    this._settings = settings;
  }

  indexUrl(): string {
    return this._baseUrl;
  }
  detailUrl(externalId: string): string {
    return this._makeUrl('externalDetailEndpoint').replace(
      '{externalId}',
      externalId
    );
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
  tracker: WidgetTracker<MainAreaWidget<ArtifactSharingWidget>>,
  artifactRegistry: IArtifactRegistry,
  browserHelper: FileBrowserHelper
) {
  let widget: MainAreaWidget<ArtifactSharingWidget>;

  return async (workflow: Workflow) => {
    const artifact = await browserHelper.currentItemArtifact();

    if (!widget || widget.isDisposed) {
      const urlFactory = new ArtifactSharingURL(settings);
      const content = new ArtifactSharingWidget(
        artifact,
        workflow,
        urlFactory,
        artifactRegistry
      );
      content.title.label =
        workflow === 'upload' ? 'Package artifact' : 'Edit artifact';
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
  id: WIDGET_PLUGIN_ID,
  requires: [
    ISettingRegistry,
    ICommandPalette,
    ILayoutRestorer,
    IMainMenu,
    IFileBrowserFactory,
    IArtifactRegistry
  ],
  activate(
    app: JupyterFrontEnd,
    settingRegistry: ISettingRegistry,
    palette: ICommandPalette,
    restorer: ILayoutRestorer,
    mainMenu: IMainMenu,
    fileBrowserFactory: IFileBrowserFactory,
    artifactRegistry: IArtifactRegistry
  ): void {
    Promise.all([
      settingRegistry.load(WIDGET_PLUGIN_ID),
      app.restored,
      artifactRegistry.getArtifacts()
        .catch((err) => {
          console.error('Error fetching list of local artifacts, defaulting to empty list.');
          return [];
        })
    ])
      .then(async ([settings]) => {
        const browser = fileBrowserFactory.defaultBrowser;
        const tracker = new WidgetTracker<
          MainAreaWidget<ArtifactSharingWidget>
        >({
          namespace: 'artifact-sharing'
        });

        const browserHelper = new FileBrowserHelper(browser, artifactRegistry);
        const openWidget = createOpener(
          app,
          settings,
          tracker,
          artifactRegistry,
          browserHelper
        );

        const enableEdit = () => {
          const item = browserHelper.currentItem();
          return (
            browserHelper.canBeArtifact(item) &&
            browserHelper.isOwnedArtifact(item)
          );
        };

        const enableCreate = () => {
          const item = browserHelper.currentItem();
          return (
            browserHelper.canBeArtifact(item) &&
            !browserHelper.isOwnedArtifact(item)
          );
        };

        app.commands.addCommand(CommandIDs.create, {
          label: 'Package as new artifact',
          isEnabled: enableCreate,
          async execute() {
            await openWidget('upload');
          }
        });

        app.commands.addCommand(CommandIDs.newVersion, {
          label: 'Create new artifact version',
          isEnabled: enableEdit,
          async execute() {
            await openWidget('upload');
          }
        });

        app.commands.addCommand(CommandIDs.edit, {
          label: 'Edit artifact',
          isEnabled: enableEdit,
          async execute() {
            await openWidget('edit');
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
        console.trace();
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
    '.jp-DirListing-item[data-isdir=true][data-artifact-id]';
  const selectorNotPublished =
    '.jp-DirListing-item[data-isdir=true]:not([data-artifact-id])';

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

class FileBrowserHelper {
  constructor(browser: FileBrowser, artifactRegistry: IArtifactRegistry) {
    this._browser = browser;
    this._artifactRegistry = artifactRegistry;
  }

  canBeArtifact(item: Contents.IModel) {
    return item && item.type === 'directory';
  }

  isOwnedArtifact(item: Contents.IModel) {
    const artifact = this._artifactRegistry.getArtifactSync(item.path);
    return artifact && artifact.ownership === 'own';
  }

  async currentItemArtifact() {
    const item = this.currentItem();
    if (!item || item.type !== 'directory') {
      return null;
    }
    let artifact = await this._artifactRegistry.getArtifact(item.path);
    if (!artifact) {
      // Generate a new placeholder artifact for the given path.
      artifact = {
        title: "",
        short_description: "",
        authors: [],
        linked_projects: [],
        reproducibility: { enable_requests: false },
        tags: [],
        versions: [],
        newLinks: [],
        path: item.path,
        ownership: "fork"
      };
    }
    return artifact;
  }

  currentItem() {
    const selectedItems = toArray(this._browser.selectedItems());
    if (selectedItems.length > 1) {
      // Fail on multiple items selected
      return null;
    } else if (selectedItems.length === 1) {
      return selectedItems[0];
    }

    return this._fakeCurrentRootItem();
  }

  /**
   * Provides a fake Contents.IModel entity for the current directory the
   * browser model is on. The browser model does not supply this over a public
   * interface. For our purposes, we only really need the path anyways, so it
   * is OK. Additionally, the model is always simple as it must necessarily
   * be of type='directory'.
   */
  _fakeCurrentRootItem(): Contents.IModel {
    const { path } = this._browser.model;
    return {
      content: null,
      created: null,
      format: 'json',
      last_modified: null,
      mimetype: null,
      name: path,
      path,
      type: 'directory',
      writable: true
    };
  }

  private _browser: FileBrowser;
  private _artifactRegistry: IArtifactRegistry;
}

const fileBrowserFactoryPlugin: JupyterFrontEndPlugin<IFileBrowserFactory> = {
  id: FILE_BROWSER_PLUGIN_ID,
  provides: IFileBrowserFactory,
  requires: [IDocumentManager, ITranslator, IArtifactRegistry],
  optional: [IStateDB, IRouter, JupyterFrontEnd.ITreeResolver],
  async activate(
    app: JupyterFrontEnd,
    docManager: IDocumentManager,
    translator: ITranslator,
    artifactRegistry: IArtifactRegistry,
    state: IStateDB | null,
    router: IRouter | null,
    tree: JupyterFrontEnd.ITreeResolver | null
  ): Promise<IFileBrowserFactory> {
    // NOTE(jason): in order for us to have control over the rendering/styling
    // of the default JupyterLab file browser, we need control of the `renderer`
    // that is passed in to the FileBrowser widget. Unfortunately, this is not
    // surfaced to us in any easy way in JLab 2.x. But, the renderer does
    // default in any case I could find to `DirListing.defaultRenderer`. So, by
    // overriding that _before_ any widget that needs it is created, we can
    // get where we need to be.
    //
    // This factory plugin exists just so that we can defer the loading of the
    // file browser until after we shim the `defaultRenderer`.
    //
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore: ignore our hacky overriding of a readonly property.
    DirListing.defaultRenderer = new DirListingRenderer(artifactRegistry);
    // Find the existing FileBrowser factory plugin
    const factoryPlugin: JupyterFrontEndPlugin<IFileBrowserFactory> = fileBrowserPlugins.find(
      ({ id }) => {
        return id === '@jupyterlab/filebrowser-extension:factory';
      }
    );
    return factoryPlugin.activate(
      app,
      docManager,
      translator,
      state,
      router,
      tree
    );
  }
};

const artifactRegistryPlugin: JupyterFrontEndPlugin<IArtifactRegistry> = {
  id: REGISTRY_PLUGIN_ID,
  provides: IArtifactRegistry,
  requires: [],
  activate(app: JupyterFrontEnd) {
    return new ArtifactRegistry();
  }
};

export default [plugin, fileBrowserFactoryPlugin, artifactRegistryPlugin];
