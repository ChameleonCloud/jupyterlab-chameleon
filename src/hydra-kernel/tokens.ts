import { ICellModel } from '@jupyterlab/cells';
import { IObservableList } from '@jupyterlab/observables';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import { Token } from '@lumino/coreutils';

export interface IBindingModel {
  readonly name: string;
  readonly kernel?: string;
  readonly mimeType?: string;
  readonly connection:
    | IBindingModel.ILocalConnection
    | IBindingModel.ISSHConnection
    | IBindingModel.IZunConnection;
  readonly state:
    | 'connected'
    | 'disconnected'
    | 'interrupted'
    | 'creating'
    | 'error';
  readonly progress: IBindingProgress;
}

export interface IBindingProgress {
  readonly progress: string;
  readonly progressRatio?: number;
}

export declare namespace IBindingModel {
  interface ILocalConnection {
    readonly type: 'local';
  }
  interface ISSHConnection {
    readonly type: 'ssh';
    readonly host: string;
    readonly user?: string;
    readonly privateKeyFile?: string;
  }
  interface IZunConnection {
    readonly type: 'zun';
    readonly containerUuid: string;
  }
}

export interface ICellMetadata {
  hasBinding(cell: ICellModel): boolean;
  setBindingName(cell: ICellModel, name: string): void;
  removeBinding(cell: ICellModel): void;
  getBindingName(cell: ICellModel): string;
  onBindingNameChanged(cell: ICellModel, fn: () => void): void;
}

export const IBindingRegistry = new Token<IBindingRegistry>(
  '@chameleoncloud/jupyter-chameleon:IBindingRegistry'
);

export interface IBindingRegistry {
  register(kernel: IKernelConnection): IObservableList<IBindingModel>;
  unregister(kernel: IKernelConnection): void;
  getBindings(kernel: IKernelConnection): IObservableList<IBindingModel>;
}
