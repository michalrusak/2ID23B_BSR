import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RouterEnum } from 'src/enums/router.enum';
import { HomeComponent } from './home.component';

const routes: Routes = [{ path: RouterEnum.home, component: HomeComponent }];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class HomeRoutingModule {}
