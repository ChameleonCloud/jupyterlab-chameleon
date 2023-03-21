import { ArtifactForm } from './artifact-form';

import { Button, ControlGroup, InputGroup } from '@blueprintjs/core';
import * as React from 'react';

export class ArtifactAuthorComponent extends React.Component<ArtifactForm.AuthorProps> {
  constructor(props: ArtifactForm.AuthorProps) {
    super(props);
  }

  hasAnyInput(): boolean {
    const author = this.props.author;
    return author.email !== "" || author.affiliation !== "" || author.full_name !== "";
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
          required={this.hasAnyInput()}
          value={author.affiliation}
          onChange={this.props.onFieldChange('affiliation')} />
        <Button icon='trash' small={true} onClick={onDelete}>Delete</Button>
      </ControlGroup>
      // <div className="authorInput">
      //   <label>
      //     <p>Full Name</p>
      //     <input
      //       name="author_full_name"
      //       type="text"
      //       className={Classes.INPUT}
      //       placeholder="The author's full name"
      //       required={this.hasAnyInput()}
      //       value={author.full_name}
      //       onChange={this.props.onFieldChange("full_name")}
      //       disabled={this.props.disabled}
      //     />
      //   </label>
      //   <label>
      //     <p>E-Mail Address</p>
      //     <input
      //       name="author_email"
      //       type="email"
      //       className={Classes.INPUT}
      //       placeholder="The author's e-mail address"
      //       required={this.hasAnyInput()}
      //       value={author.email}
      //       onChange={this.props.onFieldChange("email")}
      //       disabled={this.props.disabled}
      //     />
      //   </label>
      //   <label>
      //     <p>Affiliation</p>
      //     <input
      //       name="author_affiliation"
      //       type="text"
      //       className={Classes.INPUT}
      //       placeholder="The organization or group with which the author is affiliated"
      //       value={author.affiliation}
      //       onChange={this.props.onFieldChange("affiliation")}
      //       disabled={this.props.disabled}
      //     />
      //   </label>
      // </div>
    )
  }
}
