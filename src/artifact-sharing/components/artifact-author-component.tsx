import { ArtifactForm } from './artifact-form';

import { Button, ControlGroup, InputGroup } from '@blueprintjs/core';
import * as React from 'react';

export class ArtifactAuthorComponent extends React.Component<ArtifactForm.AuthorProps> {
  constructor(props: ArtifactForm.AuthorProps) {
    super(props);
  }

  hasAnyInput(): boolean {
    const author = this.props.author;
    return author.email !== "" || author.full_name !== "";
  }

  render(): JSX.Element {
    const author = this.props.author;
    const onDelete = () => this.props.onDelete();
    return (
      <ControlGroup fill={true}>
        <InputGroup
          placeholder='Full name'
          required={this.hasAnyInput()}
          value={author.full_name}
          onChange={this.props.onFieldChange('full_name')} />
        <InputGroup
          placeholder='Email address'
          required={this.hasAnyInput()}
          value={author.email}
          onChange={this.props.onFieldChange('email')} />
        <InputGroup
          placeholder='Affiliation'
          value={author.affiliation}
          onChange={this.props.onFieldChange('affiliation')} />
        <Button icon='trash' small={true} onClick={onDelete}>Delete</Button>
      </ControlGroup>
    )
  }
}
