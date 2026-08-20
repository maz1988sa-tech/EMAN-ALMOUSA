// Connection details for the hosted database.
//
// The publishable key is meant to ship in the browser: it grants only what
// row-level security allows the `anon` role to do, which here is reading the
// price list and the published working hours, and calling the booking
// functions. It cannot read the client list. See supabase/migrations.
window.APP_CONFIG = {
  SUPABASE_URL: '__SUPABASE_URL__',
  SUPABASE_KEY: '__SUPABASE_PUBLISHABLE_KEY__',

  // Falls back to the value stored in the database; used before settings load.
  BUSINESS_NAME: 'إيمان آل موسى',
  TIMEZONE: 'Asia/Riyadh',
};
