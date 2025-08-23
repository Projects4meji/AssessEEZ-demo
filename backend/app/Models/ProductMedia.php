<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class ProductMedia extends Model
{
    use HasFactory;

    protected $fillable = [
        'id',
        'media',
        'product_id',
        'type',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
