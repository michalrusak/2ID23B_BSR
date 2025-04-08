import { NgModule } from '@angular/core';

import { SharedModule } from '../shared/shared.module';
import { PhotoRoutingModule } from './photo-routing.module';
import { AddPhotoComponent } from './components/add-photo/add-photo.component';
import { PhotoListComponent } from './components/photo-list/photo-list.component';

@NgModule({
  declarations: [AddPhotoComponent, PhotoListComponent],
  imports: [SharedModule, PhotoRoutingModule],
})
export class PhotoModule {}
