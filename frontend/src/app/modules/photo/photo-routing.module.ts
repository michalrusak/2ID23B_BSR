import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RouterEnum } from 'src/enums/router.enum';
import { AddPhotoComponent } from './components/add-photo/add-photo.component';
import { PhotoListComponent } from './components/photo-list/photo-list.component';

const routes: Routes = [
  {
    path: RouterEnum.addPhoto,
    component: AddPhotoComponent,
  },
  {
    path: RouterEnum.photos,
    component: PhotoListComponent,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class PhotoRoutingModule {}
