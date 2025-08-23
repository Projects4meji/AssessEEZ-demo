<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Customer extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'name',
        'email',
        'customer_id',
        'price',
        'payment_terms',
        'customer_address',
        'billing_address',
        'vat',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
