import type {ButtonHTMLAttributes} from 'react';

import clsx from 'clsx';

export function Button({
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={clsx(
        'rounded-xl bg-blue-600 px-4 py-2 font-medium text-white',
        className
      )}
      {...props}
    />
  );
}
