import { Component } from '@angular/core';
import { Store } from '@ngrx/store';
import { Observable } from 'rxjs';

import { RouterEnum } from 'src/enums/router.enum';
import { User } from '../../models/models';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
})
export class HeaderComponent {
  constructor(private authService: AuthService) {}

  user$: Observable<String | null> = this.authService.currentUser$;

  RouterEnum = RouterEnum;

  logout() {
    this.authService.logout();
  }
}
