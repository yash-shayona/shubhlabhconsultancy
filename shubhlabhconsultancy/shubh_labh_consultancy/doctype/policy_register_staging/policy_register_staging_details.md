# Policy Register Staging Validation and Posting Flow

## Validate Pending Records

- **Check Staging Write permission**  
  Current user ke paas `Policy Register Staging` DocType ki Write permission honi chahiye. Permission nahi hui toh validation start nahi hogi.

- **Find all outstanding non-ignored/non-posted records**  
  Validation ke liye woh records select hote hain jinke:
  - `posted_policy_register` blank ho
  - `ignore_record = 0` ho
  - `processing_status` Processed, Processing ya Ignored na ho

- **Mark records Processing**  
  Background job start karne se pehle eligible records ka `processing_status = Processing` set kiya jaata hai.

- **Run background job**  
  Validation synchronous request mein nahi chalti. Records long background queue mein process hote hain, taaki large imports ke time browser request timeout na ho.

- **Skip newly ignored records**  
  Agar background job start hone ke baad record Ignore kar diya gaya ho, toh validation skip hoti hai aur status `Ignored` set hota hai.

- **Skip already posted records**  
  Agar staging record ka `posted_policy_register` already set ho, toh usko dobara validate ya process nahi kiya jaata.

- **Recover existing submitted final link**  
  Agar staging mein final link blank hai, lekin submitted `Policy Register` mein same `source_staging` mil jaata hai, toh existing final document ka link staging mein restore karke status `Processed` set hota hai.

- **Normalize policy, endorsement, insurer and customer values**  
  In fields ko duplicate checking ke liye normalize kiya jaata hai:
  - Policy Number
  - Endorsement Number
  - Insurer Name
  - Customer Name

  Normalization mein:
  - Value uppercase hoti hai
  - Leading/trailing spaces remove hote hain
  - Letters aur numbers ke alawa symbols remove hote hain

  Example:

  `POLICY / 123-A` → `POLICY123A`

- **Generate SHA-256 fingerprint**  
  Record ka unique comparison fingerprint in values se banta hai:
  - Normalized Policy Number
  - Normalized Endorsement Number
  - Normalized Insurer Name
  - Normalized Customer Name
  - Business Month
  - CNO
  - Total Brokerage and Reward

  In sab values ko combine karke SHA-256 hash generate hota hai aur `record_fingerprint` mein store hota hai. Ye staging duplicate identify karne ke liye use hota hai.

- **Validate Business Month**  
  `business_month` required hai aur valid date honi chahiye.

- **Validate Start Date**  
  `start_date` required hai aur valid date honi chahiye.

- **Validate Expiry Date**  
  `expiry_date` required hai aur valid date honi chahiye.

- **Validate CNO greater than zero**  
  CNO missing, zero ya negative nahi hona chahiye. System usko positive integer value ke roop mein check karta hai.

- **Require Policy Number**  
  Policy Number blank nahi hona chahiye.

- **Require Policy Type**  
  Policy Type blank nahi hona chahiye. Current validation sirf required check karti hai; kisi specific Policy Type list ko validate nahi karti.

- **Require Insurer Name**  
  Insurer Name blank nahi hona chahiye.

- **Require Customer Name**  
  Customer Name blank nahi hona chahiye.

- **Ensure Expiry Date is on or after Start Date**  
  Expiry Date, Start Date se pehle nahi ho sakti.

- **Ensure Share Percentage is between 1 and 100**  
  Share Percentage minimum `1` aur maximum `100` honi chahiye. Decimal percentage allowed hai, jaise `15.50`, `37.25` ya `99.99`.

- **Ensure Business Type is New or Renewal**  
  Exact allowed values:
  - `New`
  - `Renewal`

  Comparison case-sensitive hai.

- **Warn if Endorsement Number is blank**  
  Blank Endorsement Number blocking error nahi hai. Record `Warning` status mein jaata hai.

- **Warn if selected amounts are zero**  
  In fields mein se koi zero ho toh warning aati hai:
  - Brokerage Premium
  - Brokerage Amount
  - Total Brokerage

- **Warn if financial amounts are negative**  
  In fields mein negative value ho toh warning aati hai:
  - Brokerage Premium
  - Brokerage Amount
  - TP Premium
  - TP Brokerage Amount
  - Total Brokerage
  - Total Brokerage and Reward

  Negative values cancellation, reversal ya adjustment represent kar sakti hain, isliye ye blocking error nahi hai.

- **Warn if Brokerage Percentage exceeds 100**  
  `brokerage_percentage > 100` hone par warning aati hai.

- **Warn if TP Brokerage Percentage exceeds 100**  
  `tp_brokerage_percentage > 100` hone par warning aati hai.

- **Warn if Policy Period does not overlap Business Month**  
  Selected Business Month ka first aur last day nikala jaata hai. Agar poora policy period us month ke bahar ho, toh warning aati hai.

  Example:  
  Business Month June hai, lekin Policy Start Date July mein hai, toh warning aayegi.

- **Warn if Brokerage Amount calculation does not match**  
  Expected Brokerage Amount calculate hota hai:

  `Brokerage Premium × Brokerage Percentage ÷ 100`

  Calculated amount ko imported `brokerage_amount` se configured rounding/tolerance rule ke through compare kiya jaata hai. Meaningful mismatch ho toh warning aati hai.

- **Warn if TP Brokerage Amount calculation does not match**  
  Expected TP Brokerage Amount calculate hota hai:

  `TP Premium × TP Brokerage Percentage ÷ 100`

  Isko imported `tp_brokerage_amount` se compare kiya jaata hai.

- **Warn if Total Brokerage calculation does not match**  
  Expected Total Brokerage calculate hota hai:

  `Brokerage Amount + TP Brokerage Amount`

  Isko imported `total_brokerage` se compare kiya jaata hai.

- **Warn if Total Brokerage and Reward is lower than Total Brokerage**  
  Agar:

  `Total Brokerage and Reward < Total Brokerage`

  toh warning aati hai.

- **Check staging duplicate**  
  System kisi doosre `Policy Register Staging` record mein same `record_fingerprint` search karta hai.

  Current duplicate query ignored, invalid ya processed staging records ko separately exclude nahi karti. Same fingerprint wala koi bhi doosra staging record duplicate warning cause kar sakta hai.

- **Check submitted final duplicate**  
  Submitted `Policy Register` mein duplicate check in fields se hota hai:
  - Policy Number
  - Insurer Name
  - Business Month
  - Expected Brokerage

  Agar Endorsement Number available ho, toh woh bhi duplicate filter mein include hota hai.

  Customer Name aur CNO final duplicate check mein currently include nahi hain.

- **Set Valid, Warning or Invalid status**  
  Final validation result:
  - Error present → `Invalid`
  - No error, but warning present → `Warning`
  - No error and no warning → `Valid`

- **Set Ready or Not Processed status**  
  Processing status:
  - `Valid` → `Ready`
  - `Warning` → `Ready`
  - `Invalid` → `Not Processed`

- **Store validation messages**  
  Saare errors aur warnings newline-separated `validation_messages` field mein save hote hain.

  Format:

  `ERROR: <message>`  
  `WARNING: <message>`

- **Store duplicate and warning flags**  
  Validation result ke according:
  - `has_warning = 1` when warnings exist
  - `is_duplicate = 1` when possible duplicate exists

- **Handle unexpected validation failure**  
  Code-level exception aane par:
  - `validation_status = Invalid`
  - `processing_status = Failed`
  - Error message staging record mein save hota hai
  - Full traceback Frappe Error Log mein store hota hai

---

## Post Valid Records

- **Check Staging Write permission**  
  Current user ke paas `Policy Register Staging` par Write permission honi chahiye.

- **Check Policy Register Create permission**  
  Current user ke paas final `Policy Register` create karne ki permission honi chahiye.

- **Check Policy Register Submit permission**  
  Current user ke paas final `Policy Register` submit karne ki permission honi chahiye.

- **Select only Valid and Ready records**  
  Current configuration mein sirf woh staging records post hote hain jinke:
  - `validation_status = Valid`
  - `processing_status = Ready`

  `Warning` records current code mein post nahi hote.

- **Exclude ignored records**  
  `ignore_record = 1` wale records posting candidates mein include nahi hote.

- **Exclude already linked records**  
  Jinka `posted_policy_register` already set hai, unke liye naya final Policy Register create nahi hota.

- **Mark candidates Processing**  
  Background posting job start hone se pehle candidates ka `processing_status = Processing` set hota hai.

- **Check Ignore status again**  
  Background job ke andar Ignore status dobara check hota hai. Agar record meanwhile Ignore hua ho, toh posting skip hoti hai aur status `Ignored` set hota hai.

- **Check posted link again**  
  Background job ke andar `posted_policy_register` dobara check hota hai, taaki same staging record accidentally twice post na ho.

- **Check final document using source_staging**  
  System final `Policy Register` table mein check karta hai:

  `source_staging = current staging record`

  Ye one staging record se multiple final documents banne se protect karta hai.

- **Recover submitted existing final document**  
  Agar same `source_staging` wala submitted Policy Register already mil jaaye, toh naya document create nahi hota.

  Existing final link staging mein restore hota hai aur staging `Processed` mark hoti hai.

- **Block if draft final document already exists**  
  Agar same staging record ke against draft Policy Register milta hai, toh posting fail hoti hai. System silently second document create nahi karta.

- **Run complete revalidation again**  
  Posting se pehle staging record par complete validation dobara chalti hai.

  Isse protection milti hai agar:
  - Validate button ke baad data change hua ho
  - Duplicate final document meanwhile create hua ho
  - Record warning ya invalid ban gaya ho

- **Allow only Valid revalidation result**  
  Revalidation ke baad result exact `Valid` hona chahiye.

  Revalidation result:
  - `Warning` → posting skip
  - `Invalid` → posting skip
  - `Valid` → posting continue

- **Create one Policy Register per staging record**  
  Har accepted staging record ke liye exactly one final `Policy Register` document create hota hai.

- **Copy staging business fields**  
  Staging se final Policy Register mein ye fields copy hoti hain:
  - Business Month
  - Financial Year
  - CNO
  - Policy Type
  - Policy Number
  - Endorsement Number
  - Start Date
  - Expiry Date
  - Share Percentage
  - Brokerage Premium
  - Brokerage Percentage
  - Brokerage Amount
  - TP Premium
  - TP Brokerage Percentage
  - TP Brokerage Amount
  - Total Brokerage
  - Total Brokerage and Reward
  - Business Type
  - Insurer Name
  - Customer Name
  - Campaign Name

- **Attach source staging record**  
  Final Policy Register mein:

  `source_staging = staging record name`

  store hota hai, jisse final record ka original source trace kiya ja sake.

- **Attach latest successful Data Import**  
  System `Data Import Log` mein current staging record ka latest successful import search karta hai.

  Final Policy Register mein:

  `source_data_import = latest successful Data Import`

  store hota hai.

  Agar successful Data Import Log nahi milta, toh current code posting ko block nahi karta.

- **Initialize reconciliation amounts**  
  Final Policy Register create karte waqt:
  - `expected_brokerage = total_brokerage_and_reward`
  - `settled_brokerage = 0`
  - `written_off_brokerage = 0`
  - `outstanding_brokerage = total_brokerage_and_reward`
  - `reconciliation_status = Pending`

- **Insert Policy Register**  
  Final Policy Register database mein insert hota hai.

- **Submit Policy Register**  
  Insert ke immediately baad Policy Register submit hota hai. Reconciliation flow ke liye final record submitted state mein create hota hai.

- **Update staging as Processed**  
  Successful posting ke baad staging record ka:

  `processing_status = Processed`

  set hota hai.

- **Store final document link**  
  Created Policy Register ka document name:

  `posted_policy_register`

  field mein save hota hai.

- **Store processed user and datetime**  
  Staging mein:
  - `processed_by = posting request start karne wala user`
  - `processed_on = current datetime`

  store hota hai.

- **Rollback individual failed record**  
  Har record ke liye separate database savepoint use hota hai. Ek record fail hone par sirf us record ke changes rollback hote hain; baaki batch processing continue karti hai.

- **Mark failed posting as Failed**  
  Posting exception aane par:
  - `processing_status = Failed`
  - Existing validation messages ke saath posting error append hota hai
  - Full traceback Frappe Error Log mein save hota hai

- **Commit records in batches**  
  Large imports ke liye records batches mein commit hote hain, taaki ek bahut large transaction create na ho.

- **Publish realtime summary**  
  Job complete hone par current user ko realtime popup milta hai.

  Validation summary mein:
  - Total
  - Valid
  - Warning
  - Invalid
  - Ignored
  - Failed

  Posting summary mein:
  - Total
  - Posted
  - Already Processed
  - Not Eligible
  - Failed

## Important Current Behaviour

- Validate aur Post buttons checkbox-selected records use nahi karte. Ye automatically all eligible records process karte hain.
- Warning records ka `processing_status = Ready` hota hai, lekin current configuration mein Warning records post nahi hote.
- Posting ke time full validation dobara chalti hai.
- Same staging record se second Policy Register create karna blocked hai.
- Possible business duplicate warning hai; same staging source se duplicate posting hard block hai.
- Uploaded amounts automatically replace ya correct nahi hote. System sirf mismatch warning show karta hai.