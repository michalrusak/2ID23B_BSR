import { Component } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { NotifierService } from 'angular-notifier';
import { AuthService } from 'src/app/modules/core/services/auth.service';
import { RouterEnum } from 'src/enums/router.enum';

@Component({
  selector: 'app-register',
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.scss'],
})
export class RegisterComponent {
  constructor(
    private authService: AuthService,
    private router: Router,
    private notifierService: NotifierService
  ) {}
  RouterEnum = RouterEnum;

  form = new FormGroup({
    username: new FormControl('', {
      validators: [
        Validators.required,
        Validators.minLength(3),
        Validators.maxLength(30),
      ],
      nonNullable: true,
    }),
    password: new FormControl('', {
      validators: [
        Validators.required,
        Validators.minLength(8),
        Validators.maxLength(30),
      ],
      nonNullable: true,
    }),
  });

  get controls() {
    return this.form.controls;
  }

  getErrorMessage(control: FormControl) {
    if (control.hasError('required')) {
      return 'This field is required!';
    }
    if (control.hasError('minlength')) {
      return 'Not enough character!';
    }
    if (control.hasError('maxlength')) {
      return 'Too many characters';
    }
    if (control.hasError('email')) {
      return 'Email is not valid!';
    }

    return '';
  }

  onSubmit() {
    const { username, password } = this.form.getRawValue();
    this.authService.register(username, password).subscribe({
      next: () => {
        this.router.navigate([RouterEnum.login]);
        this.notifierService.notify(
          'success',
          'Register success, you can login!'
        );
      },
      error: (err) => this.notifierService.notify('error', 'Try again!'),
    });
  }
}
