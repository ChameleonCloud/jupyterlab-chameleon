import * as React from 'react';
import { ChangeEvent } from 'react';
import { Button, FormGroup } from '@blueprintjs/core';

import { ArtifactForm } from './artifact-form';

export class ArtifactDynamicLengthList<E extends JSX.Element, T> extends React.Component<ArtifactForm.ListProps<E, T>> {
  static defaultProps: { disabled: false };

  constructor(props: ArtifactForm.ListProps<E, T>) {
    super(props);
    const initialList = this.props.list;
    this.state = { list: initialList.length > 0 ? initialList : [this.props.newObjectGenerator()] };
  }

  addItem() {
    return () => {
      let copy = [...this.props.list, this.props.newObjectGenerator()];
      return this.props.artifactUpdater(copy);
    };
  }

  removeItem(index: number) {
    return () => {
      let copy = [...this.props.list];
      copy.splice(index, 1);
      return this.props.artifactUpdater(copy);
    }
  }

  updateItem(index: number) {
    return (field: string) => {
      return (event: ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        let newList = [...this.props.list]
        newList[index] = { ...newList[index], [field]: value }
        return this.props.artifactUpdater(newList);
      };
    };
  }

  getListForComponents(): Array<T> {
    if (this.props.list.length < 1) {
      return [this.props.newObjectGenerator()];
    } else {
      return this.props.list;
    }
  }

  render() {
    return (
      <FormGroup className='chi-ListComponent'
        label={this.props.label}
        labelInfo={this.props.labelInfo}
        helperText={this.props.helperText}>
        {this.getListForComponents().map((item, index) => (
          <div className='chi-ListComponent-Item' key={index}>
            {this.props.newComponentGenerator(item, this.updateItem(index), this.removeItem(index))}
          </div>
        )
        )}
        <Button small={true} onClick={this.addItem()} icon='plus'>Add author</Button>
      </FormGroup>
    )
  }
}
